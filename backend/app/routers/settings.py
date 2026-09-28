from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..data_availability import AVAILABLE, UNAVAILABLE
from ..db import get_db
from ..deps import KEYWORD_BUDGET, PROFILE_BUDGET
from ..threads import oauth
from ..threads.errors import ThreadsAPIError
from ..utils import to_aware
from ..services.app_config import AppConfig, load_config, save_config

router = APIRouter(prefix="/api/settings", tags=["settings"])

REQUIRED_SCOPES = ["threads_basic", "threads_keyword_search", "threads_profile_discovery"]


def _connection_status(db: Session) -> dict:
    settings = get_settings()
    conn = oauth.get_connection(db)
    manual = bool(settings.threads_access_token.get_secret_value())
    scopes = (conn.scopes if conn else None) or None
    return {
        "app_configured": bool(settings.threads_app_id and settings.threads_app_secret.get_secret_value()),
        "connected": bool(conn) or manual,
        "token_source": "oauth" if conn else ("env" if manual else None),
        "username": conn.username if conn else None,
        "threads_user_id": conn.threads_user_id if conn else None,
        "expires_at": to_aware(conn.expires_at) if conn else None,
        "last_refreshed_at": to_aware(conn.last_refreshed_at) if conn else None,
        "granted_scopes": scopes,
        "requested_scopes": settings.threads_scopes.split(","),
        "missing_scopes": [s for s in REQUIRED_SCOPES if scopes is not None and s not in scopes],
        "redirect_uri": settings.threads_redirect_uri,
        "keyword_search_budget_remaining": KEYWORD_BUDGET.remaining,
        "profile_budget_remaining": PROFILE_BUDGET.remaining,
    }


@router.get("")
def get_all(db: Session = Depends(get_db)):
    settings = get_settings()
    return {
        "config": load_config(db).model_dump(),
        "threads": _connection_status(db),
        "embedding_model": settings.embedding_model,
        "data_availability": {"available": AVAILABLE, "unavailable": UNAVAILABLE},
    }


@router.put("")
def update_config(cfg: AppConfig, db: Session = Depends(get_db)):
    return {"config": save_config(db, cfg).model_dump()}


@router.post("/reset")
def reset_config(db: Session = Depends(get_db)):
    return {"config": save_config(db, AppConfig()).model_dump()}


@router.get("/data-availability")
def data_availability():
    return {"available": AVAILABLE, "unavailable": UNAVAILABLE}


@router.post("/test-connection")
async def test_connection(request: Request, db: Session = Depends(get_db)):
    client = request.app.state.client_factory(db)
    try:
        me = await client.me()
    except ThreadsAPIError as exc:
        return {"ok": False, **exc.to_dict()}
    return {"ok": True, "username": me.get("username"), "id": me.get("id")}


class KeywordTest(BaseModel):
    q: str = Field(min_length=1, max_length=100)
    search_type: str = Field("TOP", pattern="^(TOP|RECENT)$")


@router.post("/test-keyword-search")
async def test_keyword_search(body: KeywordTest, request: Request, db: Session = Depends(get_db)):
    """Runs ONE keyword_search page (counts against the 24h budget)."""
    client = request.app.state.client_factory(db)
    try:
        posts = await client.keyword_search(body.q, search_type=body.search_type, page_size=10, max_pages=1, max_items=10)
    except ThreadsAPIError as exc:
        return {"ok": False, **exc.to_dict()}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "ok": True,
        "count": len(posts),
        "sample": [
            {k: p.get(k) for k in ("username", "text", "timestamp", "media_type", "permalink")} for p in posts
        ],
    }
