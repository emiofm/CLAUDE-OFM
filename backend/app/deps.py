"""Wiring of runtime dependencies (overridable in tests via app.state)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .services.audience import OfficialThreadsAudienceProvider
from .services.embeddings import get_embedder
from .services.images import ImageFetcher
from .services.pipeline import PipelineDeps
from .threads.client import SlidingWindowBudget, ThreadsClient
from .threads.oauth import current_token, ensure_fresh_token

_settings = get_settings()
KEYWORD_BUDGET = SlidingWindowBudget(_settings.threads_keyword_search_daily_budget)
PROFILE_BUDGET = SlidingWindowBudget(_settings.threads_profile_daily_budget)


def build_client(db: Session) -> ThreadsClient:
    settings = get_settings()

    def provider() -> str | None:
        # Fresh session so a long-running job sees refreshed tokens.
        s = SessionLocal()
        try:
            return current_token(s, settings)
        finally:
            s.close()

    return ThreadsClient(
        provider,
        graph_url=settings.threads_graph_url,
        timeout_s=settings.threads_request_timeout_s,
        keyword_budget=KEYWORD_BUDGET,
        profile_budget=PROFILE_BUDGET,
    )


async def default_deps_factory(db: Session) -> PipelineDeps:
    settings = get_settings()
    await ensure_fresh_token(db, settings)
    client = build_client(db)
    return PipelineDeps(
        client=client,
        embedder=get_embedder(settings.embedding_model, settings.embedding_device),
        fetcher=ImageFetcher(max_bytes=settings.max_image_bytes),
        audience=OfficialThreadsAudienceProvider(client),
    )


def default_client_factory(db: Session) -> ThreadsClient:
    return build_client(db)


def default_embedder_factory():
    settings = get_settings()
    return get_embedder(settings.embedding_model, settings.embedding_device)
