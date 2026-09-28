from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

FOLLOWERS_UNAVAILABLE = "Follower count unavailable from official Threads API"
METRIC_UNAVAILABLE = "Not available from official Threads API"


class SearchFilters(BaseModel):
    min_posts_7d: int | None = Field(None, ge=0)
    min_posts_30d: int | None = Field(None, ge=0)
    min_posts_90d: int | None = Field(None, ge=0)
    min_followers: int | None = Field(None, ge=0)
    max_followers: int | None = Field(None, ge=0)
    min_replies: int | None = Field(None, ge=0)
    min_likes: int | None = Field(None, ge=0)
    media_type: str | None = Field(None, pattern="^(TEXT|IMAGE|VIDEO)$")
    # When true, creators whose metric is unknown are excluded instead of flagged.
    strict_unknown_metrics: bool = False


class SearchRequest(BaseModel):
    reference_set_id: int | None = None
    keywords: list[str] = Field(min_length=1, max_length=25)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("keywords")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        out = []
        for k in v:
            k = k.strip()
            if k and k.lower() not in {x.lower() for x in out}:
                if len(k) > 100:
                    raise ValueError("keywords must be at most 100 characters")
                out.append(k)
        if not out:
            raise ValueError("at least one non-empty keyword is required")
        return out


class JobOut(BaseModel):
    id: int
    status: str
    keywords: list[str]
    filters: dict
    reference_set_id: int | None
    progress: dict | None
    error: str | None
    warnings: list[str] | None
    created_at: datetime
    completed_at: datetime | None


class Metric(BaseModel):
    """A metric value plus provenance. value=None means unavailable."""

    value: float | int | None
    available: bool
    source: str | None = None
    note: str | None = None


class PostOut(BaseModel):
    id: int
    threads_post_id: str
    text: str | None
    permalink: str | None
    timestamp: datetime | None
    media_type: str | None
    media_url: str | None


class CreatorOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    profile_url: str
    profile_picture_url: str | None
    bio: str | None
    is_verified: bool | None
    status: str
    followers: Metric
    posts_7d: Metric
    posts_30d: Metric
    posts_90d: Metric
    last_post_at: datetime | None
    profile_likes: Metric
    profile_replies: Metric
    profile_reposts: Metric
    profile_quotes: Metric
    profile_views: Metric
    creator_signal: str | None
    monetization_signal: str | None
    monetization_label: str | None
    signal_terms: list[str]


class ResultOut(BaseModel):
    id: int
    creator: CreatorOut
    latest_post: PostOut | None
    best_image_url: str | None
    visual_similarity: float | None
    best_image_similarity: float | None
    top_k_avg_similarity: float | None
    images_analyzed: int
    activity_score: float | None
    engagement_score: float | None
    creator_signal_score: float | None
    keyword_relevance: float | None
    audience_score: float | None
    total_score: float
    score_breakdown: dict | None
    matched_keywords: list[str]
    filter_flags: list[str]
