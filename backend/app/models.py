"""Database models.

Nullable metric columns are deliberate: ``None`` means "not available from
the data source", never zero. Code must not coerce these to 0.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str] = mapped_column(String(255))
    profile_picture_url: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    is_verified: Mapped[bool | None] = mapped_column()

    # Audience — only ever filled from a legitimate AudienceProvider.
    follower_count: Mapped[int | None] = mapped_column(Integer)
    follower_source: Mapped[str | None] = mapped_column(String(64))
    follower_last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Profile-level aggregate counts as returned by profile_lookup (nullable).
    profile_likes_count: Mapped[int | None] = mapped_column(Integer)
    profile_replies_count: Mapped[int | None] = mapped_column(Integer)
    profile_reposts_count: Mapped[int | None] = mapped_column(Integer)
    profile_quotes_count: Mapped[int | None] = mapped_column(Integer)
    profile_views_count: Mapped[int | None] = mapped_column(Integer)
    profile_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_lookup_status: Mapped[str | None] = mapped_column(String(32))

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posts_7d: Mapped[int | None] = mapped_column(Integer)
    posts_30d: Mapped[int | None] = mapped_column(Integer)
    posts_90d: Mapped[int | None] = mapped_column(Integer)
    # "profile_posts" = counted from the creator's public posts endpoint;
    # "keyword_search_sample" = lower bound from posts seen in search only.
    activity_source: Mapped[str | None] = mapped_column(String(32))

    creator_signal: Mapped[str | None] = mapped_column(String(16))  # none/low/medium/high
    monetization_signal: Mapped[str | None] = mapped_column(String(16))  # none/possible
    signal_terms: Mapped[list | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(16), default="new")  # new/saved/ignored
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    posts: Mapped[list["Post"]] = relationship(back_populates="creator", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    threads_post_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), index=True)
    text: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    has_replies: Mapped[bool | None] = mapped_column()
    # Per-post like/reply counts are NOT returned by keyword_search or
    # profile_posts for third-party media; they stay NULL unless a legitimate
    # source provides them.
    likes: Mapped[int | None] = mapped_column(Integer)
    replies: Mapped[int | None] = mapped_column(Integer)
    image_embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(32))  # keyword_search / profile_posts
    matched_keywords: Mapped[list | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    creator: Mapped[Creator] = relationship(back_populates="posts")


class ReferenceSet(Base):
    __tablename__ = "reference_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    centroid: Mapped[bytes | None] = mapped_column(LargeBinary)

    images: Mapped[list["ReferenceImage"]] = relationship(
        back_populates="reference_set", cascade="all, delete-orphan"
    )


class ReferenceImage(Base):
    __tablename__ = "reference_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_set_id: Mapped[int] = mapped_column(ForeignKey("reference_sets.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)

    reference_set: Mapped[ReferenceSet] = relationship(back_populates="images")


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/running/completed/failed
    reference_set_id: Mapped[int | None] = mapped_column(ForeignKey("reference_sets.id"))
    keywords: Mapped[list] = mapped_column(JSON)
    filters: Mapped[dict] = mapped_column(JSON)
    weights: Mapped[dict | None] = mapped_column(JSON)
    progress: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="search_job", cascade="all, delete-orphan"
    )


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (UniqueConstraint("search_job_id", "creator_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_job_id: Mapped[int] = mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))
    # All component scores are 0-100, or NULL when the input is unavailable.
    visual_similarity: Mapped[float | None] = mapped_column(Float)
    best_image_similarity: Mapped[float | None] = mapped_column(Float)
    top_k_avg_similarity: Mapped[float | None] = mapped_column(Float)
    images_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[float | None] = mapped_column(Float)
    engagement_score: Mapped[float | None] = mapped_column(Float)
    creator_signal: Mapped[float | None] = mapped_column(Float)
    keyword_relevance: Mapped[float | None] = mapped_column(Float)
    audience_score: Mapped[float | None] = mapped_column(Float)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    matched_keywords: Mapped[list | None] = mapped_column(JSON)
    latest_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    best_image_url: Mapped[str | None] = mapped_column(Text)
    filter_flags: Mapped[list | None] = mapped_column(JSON)

    search_job: Mapped[SearchJob] = relationship(back_populates="results")
    creator: Mapped[Creator] = relationship()
    latest_post: Mapped[Post | None] = relationship()


class ThreadsConnection(Base):
    """Server-side OAuth token storage. Tokens are never sent to the browser."""

    __tablename__ = "threads_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    threads_user_id: Mapped[str | None] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(64))
    access_token: Mapped[str] = mapped_column(Text)  # Fernet-encrypted if key configured
    token_type: Mapped[str | None] = mapped_column(String(32))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list | None] = mapped_column(JSON)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CacheEntry(Base):
    """Generic TTL cache (profile lookups, profile posts)."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[dict | list | None] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)
