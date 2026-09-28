"""Reference image sets (the user's own uploads) and their centroid embedding."""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..logging_conf import get_logger
from ..models import ReferenceImage, ReferenceSet
from ..services.embeddings import EmbeddingUnavailableError, load_image, to_bytes
from ..services.similarity import centroid

router = APIRouter(prefix="/api/reference-sets", tags=["references"])
log = get_logger("EMBEDDING")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _out(rs: ReferenceSet) -> dict:
    return {
        "id": rs.id,
        "name": rs.name,
        "created_at": rs.created_at,
        "embedding_model": rs.embedding_model,
        "images": [{"id": i.id, "url": f"/api/reference-sets/{rs.id}/images/{i.id}"} for i in rs.images],
    }


@router.post("")
async def create_reference_set(
    request: Request,
    name: str = Form("Reference model"),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not (settings.min_reference_images <= len(files) <= settings.max_reference_images):
        raise HTTPException(
            400,
            f"Upload between {settings.min_reference_images} and {settings.max_reference_images} images.",
        )
    blobs: list[tuple[str, bytes]] = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        data = await f.read()
        if ext not in ALLOWED_EXT:
            raise HTTPException(400, f"{f.filename}: only JPG, PNG or WEBP images are accepted.")
        if len(data) > settings.max_image_bytes:
            raise HTTPException(400, f"{f.filename}: image is larger than {settings.max_image_bytes} bytes.")
        try:
            load_image(data)
        except Exception:
            raise HTTPException(400, f"{f.filename}: not a valid image.") from None
        blobs.append((ext, data))

    embedder = request.app.state.embedder_factory()
    log.info("embedding reference images", count=len(blobs), model=embedder.model_name)
    try:
        vecs = await asyncio.to_thread(embedder.embed_images, [b for _, b in blobs])
    except EmbeddingUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc

    rs = ReferenceSet(name=name.strip() or "Reference model", embedding_model=embedder.model_name)
    rs.centroid = to_bytes(centroid(vecs))
    db.add(rs)
    db.flush()
    folder = Path(settings.reference_upload_dir) / str(rs.id)
    folder.mkdir(parents=True, exist_ok=True)
    for (ext, data), vec in zip(blobs, vecs):
        path = folder / f"{uuid.uuid4().hex}{ext}"
        path.write_bytes(data)
        rs.images.append(ReferenceImage(file_path=str(path), embedding=to_bytes(vec)))
    db.commit()
    return _out(rs)


@router.get("")
def list_reference_sets(db: Session = Depends(get_db)):
    sets = db.scalars(select(ReferenceSet).order_by(ReferenceSet.id.desc())).all()
    return [_out(s) for s in sets]


@router.get("/{set_id}")
def get_reference_set(set_id: int, db: Session = Depends(get_db)):
    rs = db.get(ReferenceSet, set_id)
    if not rs:
        raise HTTPException(404, "Reference set not found")
    return _out(rs)


@router.get("/{set_id}/images/{image_id}")
def get_reference_image(set_id: int, image_id: int, db: Session = Depends(get_db)):
    img = db.get(ReferenceImage, image_id)
    if not img or img.reference_set_id != set_id or not Path(img.file_path).exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(img.file_path)


@router.delete("/{set_id}")
def delete_reference_set(set_id: int, db: Session = Depends(get_db)):
    rs = db.get(ReferenceSet, set_id)
    if not rs:
        raise HTTPException(404, "Reference set not found")
    shutil.rmtree(Path(get_settings().reference_upload_dir) / str(rs.id), ignore_errors=True)
    db.delete(rs)
    db.commit()
    return {"deleted": True}
