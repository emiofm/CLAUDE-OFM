from __future__ import annotations

from .models import Creator, Post, SearchJob, SearchResult
from .schemas import (
    FOLLOWERS_UNAVAILABLE,
    METRIC_UNAVAILABLE,
    CreatorOut,
    JobOut,
    Metric,
    PostOut,
    ResultOut,
)
from .utils import to_aware


def _metric(value, source: str | None, unavailable_note: str = METRIC_UNAVAILABLE, note: str | None = None) -> Metric:
    if value is None:
        return Metric(value=None, available=False, source=None, note=unavailable_note)
    return Metric(value=value, available=True, source=source, note=note)


def creator_out(c: Creator) -> CreatorOut:
    lower = c.activity_source == "keyword_search_sample"
    act_note = "Lower bound: counted only from posts seen in keyword search" if lower else None
    act_src = c.activity_source
    prof_src = "threads_profile_lookup"
    prof_note = "Profile-level total reported by profile_lookup"
    return CreatorOut(
        id=c.id,
        username=c.username,
        display_name=c.display_name,
        profile_url=c.profile_url,
        profile_picture_url=c.profile_picture_url,
        bio=c.bio,
        is_verified=c.is_verified,
        status=c.status,
        followers=_metric(c.follower_count, c.follower_source, FOLLOWERS_UNAVAILABLE),
        posts_7d=_metric(c.posts_7d, act_src, note=act_note),
        posts_30d=_metric(c.posts_30d, act_src, note=act_note),
        posts_90d=_metric(c.posts_90d, act_src, note=act_note),
        last_post_at=to_aware(c.last_post_at),
        profile_likes=_metric(c.profile_likes_count, prof_src, note=prof_note),
        profile_replies=_metric(c.profile_replies_count, prof_src, note=prof_note),
        profile_reposts=_metric(c.profile_reposts_count, prof_src, note=prof_note),
        profile_quotes=_metric(c.profile_quotes_count, prof_src, note=prof_note),
        profile_views=_metric(c.profile_views_count, prof_src, note=prof_note),
        creator_signal=c.creator_signal,
        monetization_signal=c.monetization_signal,
        monetization_label="Possible monetization signal" if c.monetization_signal == "possible" else None,
        signal_terms=c.signal_terms or [],
    )


def post_out(p: Post | None) -> PostOut | None:
    if p is None:
        return None
    return PostOut(
        id=p.id,
        threads_post_id=p.threads_post_id,
        text=p.text,
        permalink=p.permalink,
        timestamp=to_aware(p.timestamp),
        media_type=p.media_type,
        media_url=p.media_url or p.thumbnail_url,
    )


def result_out(r: SearchResult) -> ResultOut:
    return ResultOut(
        id=r.id,
        creator=creator_out(r.creator),
        latest_post=post_out(r.latest_post),
        best_image_url=r.best_image_url,
        visual_similarity=r.visual_similarity,
        best_image_similarity=r.best_image_similarity,
        top_k_avg_similarity=r.top_k_avg_similarity,
        images_analyzed=r.images_analyzed or 0,
        activity_score=r.activity_score,
        engagement_score=r.engagement_score,
        creator_signal_score=r.creator_signal,
        keyword_relevance=r.keyword_relevance,
        audience_score=r.audience_score,
        total_score=r.total_score,
        score_breakdown=r.score_breakdown,
        matched_keywords=r.matched_keywords or [],
        filter_flags=r.filter_flags or [],
    )


def job_out(j: SearchJob) -> JobOut:
    return JobOut(
        id=j.id,
        status=j.status,
        keywords=j.keywords or [],
        filters=j.filters or {},
        reference_set_id=j.reference_set_id,
        progress=j.progress,
        error=j.error,
        warnings=j.warnings,
        created_at=to_aware(j.created_at),
        completed_at=to_aware(j.completed_at),
    )
