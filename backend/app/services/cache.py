"""Small DB-backed TTL cache for API responses (profile lookups, posts)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import CacheEntry, Post
from ..utils import to_aware, utcnow

_MISSING = object()


def cache_get(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(CacheEntry, key)
    if row is None:
        return default
    if to_aware(row.expires_at) <= utcnow():
        db.delete(row)
        db.commit()
        return default
    return row.value


def cache_set(db: Session, key: str, value: Any, ttl_hours: float) -> None:
    row = db.get(CacheEntry, key) or CacheEntry(key=key)
    row.value = value
    row.expires_at = utcnow() + timedelta(hours=ttl_hours)
    db.add(row)
    db.commit()


def purge_expired(db: Session, embedding_ttl_hours: float) -> dict[str, int]:
    """Delete expired cache rows and drop stale third-party image embeddings."""
    now = utcnow()
    n_cache = db.execute(delete(CacheEntry).where(CacheEntry.expires_at <= now)).rowcount or 0
    cutoff = now - timedelta(hours=embedding_ttl_hours)
    stale = db.query(Post).filter(Post.embedded_at.is_not(None), Post.embedded_at < cutoff).all()
    for p in stale:
        p.image_embedding = None
        p.embedded_at = None
        p.embedding_model = None
    db.commit()
    return {"cache_entries": n_cache, "embeddings": len(stale)}
