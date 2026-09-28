from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..schemas import SearchRequest
from ..models import Creator, ReferenceSet, SearchJob, SearchResult
from ..serializers import job_out, result_out
from ..services.pipeline import run_search_job
from ..utils import to_aware

router = APIRouter(prefix="/api/search", tags=["search"])

SORTS = {
    "best": lambda r: r.total_score,
    "active": lambda r: r.activity_score if r.activity_score is not None else -1,
    "engagement": lambda r: r.engagement_score if r.engagement_score is not None else -1,
    "newest": lambda r: to_aware(r.creator.last_post_at).timestamp() if r.creator.last_post_at else 0,
}


@router.post("")
def start_search(
    req: SearchRequest, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
):
    if req.reference_set_id is not None and not db.get(ReferenceSet, req.reference_set_id):
        raise HTTPException(404, "Reference set not found")
    f = req.filters
    if f.min_followers and f.max_followers and f.min_followers > f.max_followers:
        raise HTTPException(400, "min_followers must be <= max_followers")
    job = SearchJob(
        status="pending",
        keywords=req.keywords,
        filters=f.model_dump(exclude_none=True),
        reference_set_id=req.reference_set_id,
        progress={"stage": "queued"},
    )
    db.add(job)
    db.commit()
    background.add_task(run_search_job, job.id, SessionLocal, request.app.state.deps_factory)
    return job_out(job)


@router.get("")
def list_jobs(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    jobs = db.scalars(select(SearchJob).order_by(SearchJob.id.desc()).limit(limit)).all()
    return [job_out(j) for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(SearchJob, job_id)
    if not job:
        raise HTTPException(404, "Search job not found")
    return job_out(job)


@router.get("/{job_id}/results")
def get_results(
    job_id: int,
    sort: str = Query("best", pattern="^(best|active|engagement|newest)$"),
    include_ignored: bool = False,
    db: Session = Depends(get_db),
):
    job = db.get(SearchJob, job_id)
    if not job:
        raise HTTPException(404, "Search job not found")
    q = select(SearchResult).join(Creator).where(SearchResult.search_job_id == job_id)
    if not include_ignored:
        q = q.where(Creator.status != "ignored")
    results = list(db.scalars(q).all())
    results.sort(key=SORTS[sort], reverse=True)
    return {"job": job_out(job), "results": [result_out(r) for r in results]}
