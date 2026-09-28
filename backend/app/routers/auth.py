"""Threads OAuth endpoints. Secrets never leave the server."""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..logging_conf import get_logger
from ..threads import oauth
from ..threads.client import ThreadsClient
from ..threads.errors import ThreadsAPIError

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("AUTH")
STATE_COOKIE = "threads_oauth_state"


def _frontend(path: str, **params) -> str:
    base = get_settings().frontend_url.rstrip("/")
    q = f"?{urlencode(params)}" if params else ""
    return f"{base}{path}{q}"


@router.get("/threads")
def start_oauth():
    settings = get_settings()
    if not settings.threads_app_id or not settings.threads_app_secret.get_secret_value():
        raise HTTPException(
            status_code=500,
            detail="THREADS_APP_ID / THREADS_APP_SECRET are not configured on the server.",
        )
    state = oauth.new_state()
    resp = RedirectResponse(oauth.build_authorize_url(settings, state), status_code=302)
    resp.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.threads_redirect_uri.startswith("https://"),
    )
    log.info("oauth started")
    return resp


@router.get("/threads/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    expected = request.cookies.get(STATE_COOKIE)
    if error:
        log.warning("oauth denied", error=error)
        return RedirectResponse(_frontend("/settings", threads="error", reason=error_description or error))
    if not code or not state or not expected or state != expected:
        return RedirectResponse(_frontend("/settings", threads="error", reason="invalid_state"))
    code = code.split("#")[0]  # Threads may append "#_" to the code
    transport = getattr(request.app.state, "oauth_transport", None)
    try:
        tok = await oauth.exchange_code(settings, code, transport=transport)
        scopes = await oauth.debug_token_scopes(settings, tok["access_token"], transport=transport)
        conn = oauth.save_connection(
            db,
            settings,
            access_token=tok["access_token"],
            expires_in=tok.get("expires_in"),
            token_type=tok.get("token_type"),
            user_id=tok.get("user_id"),
            scopes=scopes,
        )
        try:
            me = await ThreadsClient(
                lambda: tok["access_token"], graph_url=settings.threads_graph_url, transport=transport
            ).me()
            conn.username = me.get("username")
            db.commit()
        except ThreadsAPIError:
            pass
    except ThreadsAPIError as exc:
        log.error("oauth token exchange failed", error=type(exc).__name__)
        return RedirectResponse(_frontend("/settings", threads="error", reason=exc.user_message))
    resp = RedirectResponse(_frontend("/settings", threads="connected"))
    resp.delete_cookie(STATE_COOKIE)
    log.info("oauth completed", username=conn.username)
    return resp


@router.post("/threads/refresh")
async def refresh(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    conn = oauth.get_connection(db)
    if not conn:
        raise HTTPException(status_code=400, detail="Threads is not connected.")
    try:
        body = await oauth.refresh_long_lived(
            settings,
            oauth.decrypt_token(settings, conn.access_token),
            transport=getattr(request.app.state, "oauth_transport", None),
        )
    except ThreadsAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.to_dict()) from exc
    oauth.save_connection(
        db,
        settings,
        access_token=body["access_token"],
        expires_in=body.get("expires_in"),
        token_type=body.get("token_type"),
    )
    conn = oauth.get_connection(db)
    conn.last_refreshed_at = oauth.utcnow()
    db.commit()
    return {"refreshed": True, "expires_at": conn.expires_at}


@router.post("/threads/disconnect")
def disconnect(db: Session = Depends(get_db)):
    oauth.delete_connection(db)
    return {"connected": False}
