"""Threads OAuth 2.0 flow and server-side token storage.

Flow (per Meta's Threads API "Get Access Tokens and Permissions" guide):

1. Redirect the user to ``https://threads.net/oauth/authorize`` with
   client_id, redirect_uri, scope, response_type=code, state.
2. Callback receives ``code`` -> POST ``https://graph.threads.net/oauth/access_token``
   (client_id, client_secret, grant_type=authorization_code, redirect_uri, code)
   -> short-lived token (~1h) + user_id.
3. Exchange for a long-lived token (60 days):
   GET ``https://graph.threads.net/access_token?grant_type=th_exchange_token``
4. Refresh a long-lived token that is at least 24h old and not expired:
   GET ``https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token``

Tokens live only in the database (optionally Fernet-encrypted) and are never
returned to the frontend.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..logging_conf import get_logger
from ..models import ThreadsConnection
from ..utils import to_aware, utcnow
from .errors import ThreadsAPIError, error_from_response

log = get_logger("AUTH")


# ------------------------------------------------------------------ crypto
def _fernet(settings: Settings):
    key = settings.token_encryption_key.get_secret_value()
    if not key:
        return None
    from cryptography.fernet import Fernet

    return Fernet(key.encode())


def encrypt_token(settings: Settings, token: str) -> str:
    f = _fernet(settings)
    return "enc:" + f.encrypt(token.encode()).decode() if f else token


def decrypt_token(settings: Settings, stored: str) -> str:
    if stored.startswith("enc:"):
        f = _fernet(settings)
        if not f:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY is required to decrypt the stored token")
        return f.decrypt(stored[4:].encode()).decode()
    return stored


# ------------------------------------------------------------------- oauth
def new_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorize_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.threads_app_id,
        "redirect_uri": settings.threads_redirect_uri,
        "scope": settings.threads_scopes,
        "response_type": "code",
        "state": state,
    }
    return f"{settings.threads_authorize_url}?{urlencode(params)}"


async def _request(method: str, url: str, *, transport=None, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=20.0, transport=transport) as http:
        resp = await http.request(method, url, **kwargs)
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code != 200 or not isinstance(body, dict):
        raise error_from_response(resp.status_code, body, None)
    return body


async def exchange_code(settings: Settings, code: str, transport=None) -> dict:
    base = settings.threads_api_base.rstrip("/")
    short = await _request(
        "POST",
        f"{base}/oauth/access_token",
        transport=transport,
        data={
            "client_id": settings.threads_app_id,
            "client_secret": settings.threads_app_secret.get_secret_value(),
            "grant_type": "authorization_code",
            "redirect_uri": settings.threads_redirect_uri,
            "code": code,
        },
    )
    log.info("short-lived token received", user_id=short.get("user_id"))
    long = await _request(
        "GET",
        f"{base}/access_token",
        transport=transport,
        params={
            "grant_type": "th_exchange_token",
            "client_secret": settings.threads_app_secret.get_secret_value(),
            "access_token": short["access_token"],
        },
    )
    log.info("exchanged for long-lived token", expires_in=long.get("expires_in"))
    return {
        "access_token": long["access_token"],
        "token_type": long.get("token_type"),
        "expires_in": long.get("expires_in"),
        "user_id": str(short.get("user_id") or ""),
    }


async def refresh_long_lived(settings: Settings, token: str, transport=None) -> dict:
    base = settings.threads_api_base.rstrip("/")
    return await _request(
        "GET",
        f"{base}/refresh_access_token",
        transport=transport,
        params={"grant_type": "th_refresh_token", "access_token": token},
    )


async def debug_token_scopes(settings: Settings, token: str, transport=None) -> list[str] | None:
    """Granted scopes via debug_token using the app access token (TH|id|secret)."""
    if not settings.threads_app_id or not settings.threads_app_secret.get_secret_value():
        return None
    app_token = f"TH|{settings.threads_app_id}|{settings.threads_app_secret.get_secret_value()}"
    try:
        body = await _request(
            "GET",
            f"{settings.threads_graph_url}/debug_token",
            transport=transport,
            params={"input_token": token, "access_token": app_token},
        )
    except ThreadsAPIError as exc:
        log.warning("debug_token failed", error=type(exc).__name__)
        return None
    scopes = (body.get("data") or {}).get("scopes")
    return list(scopes) if isinstance(scopes, list) else None


# ------------------------------------------------------------- persistence
def get_connection(db: Session) -> ThreadsConnection | None:
    return db.scalars(select(ThreadsConnection).order_by(ThreadsConnection.id.desc())).first()


def save_connection(
    db: Session,
    settings: Settings,
    *,
    access_token: str,
    expires_in: int | None,
    token_type: str | None,
    user_id: str | None = None,
    username: str | None = None,
    scopes: list[str] | None = None,
) -> ThreadsConnection:
    conn = get_connection(db) or ThreadsConnection(access_token="")
    conn.access_token = encrypt_token(settings, access_token)
    conn.token_type = token_type
    conn.expires_at = utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None
    if user_id:
        conn.threads_user_id = user_id
    if username:
        conn.username = username
    if scopes is not None:
        conn.scopes = scopes
    # A new token was just issued (OAuth or refresh): restart the refresh clock.
    conn.issued_at = utcnow()
    conn.last_refreshed_at = None
    db.add(conn)
    db.commit()
    return conn


def delete_connection(db: Session) -> None:
    for conn in db.scalars(select(ThreadsConnection)).all():
        db.delete(conn)
    db.commit()


def current_token(db: Session, settings: Settings) -> str | None:
    conn = get_connection(db)
    if conn and conn.access_token:
        return decrypt_token(settings, conn.access_token)
    manual = settings.threads_access_token.get_secret_value()
    return manual or None


def needs_refresh(conn: ThreadsConnection, now: datetime | None = None) -> bool:
    """Refresh when < 7 days remain and the token is at least 24h old."""
    now = now or datetime.now(timezone.utc)
    if not conn.expires_at:
        return False
    expires = to_aware(conn.expires_at)
    last = to_aware(conn.last_refreshed_at or conn.issued_at)
    return expires - now < timedelta(days=7) and now - last >= timedelta(hours=24) and expires > now


async def ensure_fresh_token(db: Session, settings: Settings, transport=None) -> None:
    conn = get_connection(db)
    if not conn or not needs_refresh(conn):
        return
    try:
        body = await refresh_long_lived(settings, decrypt_token(settings, conn.access_token), transport)
    except ThreadsAPIError as exc:
        log.warning("token refresh failed", error=type(exc).__name__)
        return
    conn.access_token = encrypt_token(settings, body["access_token"])
    if body.get("expires_in"):
        conn.expires_at = utcnow() + timedelta(seconds=int(body["expires_in"]))
    conn.last_refreshed_at = utcnow()
    db.commit()
    log.info("token refreshed")
