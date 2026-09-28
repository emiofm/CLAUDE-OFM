"""User-editable configuration (Settings page), persisted in the DB."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ..models import AppSetting

CONFIG_KEY = "config"


class ScoreWeights(BaseModel):
    visual_similarity: float = Field(45, ge=0)
    activity: float = Field(25, ge=0)
    engagement: float = Field(15, ge=0)
    creator_signal: float = Field(10, ge=0)
    keyword_relevance: float = Field(5, ge=0)
    # Only used when a legitimate follower count exists for a creator.
    audience: float = Field(0, ge=0)

    @model_validator(mode="after")
    def _non_zero(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("at least one weight must be > 0")
        return self


class SimilarityConfig(BaseModel):
    best_weight: float = Field(0.7, ge=0)
    top_k_weight: float = Field(0.3, ge=0)
    top_k: int = Field(5, ge=1, le=50)
    # Cosine window mapped to 0-100 (CLIP-like image-image cosine range).
    cosine_floor: float = Field(0.5, ge=-1, lt=1)
    cosine_ceiling: float = Field(0.95, gt=-1, le=1)

    @model_validator(mode="after")
    def _window(self):
        if self.cosine_ceiling <= self.cosine_floor:
            raise ValueError("cosine_ceiling must be greater than cosine_floor")
        return self


class ActivityConfig(BaseModel):
    weight_7d: float = Field(35, ge=0)
    weight_30d: float = Field(40, ge=0)
    weight_90d: float = Field(15, ge=0)
    weight_recency: float = Field(10, ge=0)
    # Post counts at which each window saturates (no extra credit above).
    target_7d: int = Field(5, ge=1)
    target_30d: int = Field(20, ge=1)
    target_90d: int = Field(50, ge=1)
    # Average posts/day above which the account is treated as spammy and damped.
    spam_posts_per_day: float = Field(15, gt=0)
    recency_half_life_days: float = Field(14, gt=0)


class SearchConfig(BaseModel):
    default_keywords: list[str] = Field(
        default_factory=lambda: ["content creator", "lifestyle creator", "link in bio"]
    )
    search_type: str = Field("TOP", pattern="^(TOP|RECENT)$")
    media_type: str | None = Field("IMAGE", pattern="^(TEXT|IMAGE|VIDEO)$")
    page_size: int = Field(50, ge=1, le=100)
    max_pages_per_keyword: int = Field(3, ge=1, le=20)
    max_posts_per_keyword: int = Field(150, ge=1, le=2000)
    max_results: int = Field(50, ge=1, le=500)
    max_images_per_creator: int = Field(8, ge=1, le=30)
    lookup_profiles: bool = True
    fetch_profile_posts: bool = True


class CacheConfig(BaseModel):
    profile_ttl_hours: float = Field(24, gt=0)
    posts_ttl_hours: float = Field(24, gt=0)
    embedding_ttl_hours: float = Field(168, gt=0)


class AppConfig(BaseModel):
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    similarity: SimilarityConfig = Field(default_factory=SimilarityConfig)
    activity: ActivityConfig = Field(default_factory=ActivityConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


def load_config(db: Session) -> AppConfig:
    row = db.get(AppSetting, CONFIG_KEY)
    if row and isinstance(row.value, dict):
        return AppConfig.model_validate(row.value)
    return AppConfig()


def save_config(db: Session, cfg: AppConfig) -> AppConfig:
    row = db.get(AppSetting, CONFIG_KEY) or AppSetting(key=CONFIG_KEY)
    row.value = cfg.model_dump()
    db.add(row)
    db.commit()
    return cfg
