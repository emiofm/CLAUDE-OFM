from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Creator, Post
from ..serializers import creator_out, post_out
from ..utils import utcnow

router = APIRouter(prefix="/api/creators", tags=["creators"])


def _set_status(db: Session, creator_id: int, status: str):
    c = db.get(Creator, creator_id)
    if not c:
        raise HTTPException(404, "Creator not found")
    c.status = status
    c.status_changed_at = utcnow()
    db.commit()
    return creator_out(c)


@router.post("/{creator_id}/save")
def save_creator(creator_id: int, db: Session = Depends(get_db)):
    return _set_status(db, creator_id, "saved")


@router.post("/{creator_id}/ignore")
def ignore_creator(creator_id: int, db: Session = Depends(get_db)):
    return _set_status(db, creator_id, "ignored")


@router.post("/{creator_id}/reset")
def reset_creator(creator_id: int, db: Session = Depends(get_db)):
    return _set_status(db, creator_id, "new")


@router.get("")
def list_creators(status: str = "saved", db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Creator).where(Creator.status == status).order_by(Creator.status_changed_at.desc())
    ).all()
    out = []
    for c in rows:
        latest = db.scalars(
            select(Post).where(Post.creator_id == c.id).order_by(Post.timestamp.desc()).limit(1)
        ).first()
        out.append({"creator": creator_out(c), "latest_post": post_out(latest)})
    return out
