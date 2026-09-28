"""Search pipeline: keyword search -> dedupe -> profile -> activity ->
image embeddings -> similarity -> signals -> ranking -> persisted results.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..logging_conf import get_logger
from ..models import Creator, Post, ReferenceSet, SearchJob, SearchResult
from ..threads.client import ThreadsClient
from ..threads.errors import (
    PERMISSION_CODES,
    ThreadsAPIError,
    ThreadsAuthError,
    ThreadsNotConnectedError,
    ThreadsPermissionError,
    ThreadsRateLimitError,
)
from ..utils import parse_threads_timestamp, to_aware, utcnow
from .app_config import AppConfig
from .audience import AudienceProvider, OfficialThreadsAudienceProvider
from .cache import cache_get, cache_set, purge_expired
from .dedup import CandidateCreator, dedupe_creators, rank_candidates
from .embeddings import ImageEmbedder, from_bytes, to_bytes
from .images import ImageFetcher
from .scoring import (
    FilterInput,
    activity_score,
    apply_filters,
    audience_score,
    count_activity,
    detect_signals,
    engagement_score,
    keyword_relevance,
    total_score,
)
from .similarity import aggregate_creator_similarity, cosine, cosine_to_score

log_threads = get_logger("THREADS")
log_embed = get_logger("EMBEDDING")
log_score = get_logger("SCORING")
log_job = get_logger("JOB")

IMAGE_MEDIA_TYPES = {"IMAGE", "CAROUSEL_ALBUM"}
AUTH_ERRORS = (ThreadsNotConnectedError, ThreadsAuthError)
FATAL_ERRORS = (*AUTH_ERRORS, ThreadsPermissionError)


PREFETCH_CONCURRENCY = 4
MAX_POSTS_PER_CREATOR_ANALYSED = 100


@dataclass
class Prefetched:
    profile: dict | None  # cached profile_lookup result, None if disabled/blocked
    posts: list[dict] | None  # profile_posts, None if unavailable


@dataclass
class PipelineDeps:
    client: ThreadsClient
    embedder: ImageEmbedder
    fetcher: ImageFetcher
    audience: AudienceProvider


class SearchPipeline:
    def __init__(self, db: Session, deps: PipelineDeps, cfg: AppConfig):
        self.db = db
        self.deps = deps
        self.cfg = cfg
        self.warnings: list[str] = []
        self._profile_calls_blocked = False  # set on 429 / local budget exhausted
        self._lookup_denied = False
        self._posts_denied = False

    # -------------------------------------------------------------- helpers
    def _progress(self, job: SearchJob, **kw) -> None:
        job.progress = {**(job.progress or {}), **kw}
        self.db.commit()

    def _warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    # ---------------------------------------------------------------- stages
    async def _keyword_search(self, keywords: list[str], filters: dict) -> dict[str, list[dict]]:
        s = self.cfg.search
        media_type = filters.get("media_type", s.media_type)
        out: dict[str, list[dict]] = {}
        for kw in keywords:
            key = f"kw:{kw.lower()}:{s.search_type}:{media_type}:{s.max_posts_per_keyword}"
            cached = cache_get(self.db, key)
            if cached is not None:
                log_threads.info("cache hit", keyword=kw, results=len(cached))
                out[kw] = cached
                continue
            try:
                posts = await self.deps.client.keyword_search(
                    kw,
                    search_type=s.search_type,
                    media_type=media_type,
                    page_size=s.page_size,
                    max_pages=s.max_pages_per_keyword,
                    max_items=s.max_posts_per_keyword,
                )
            except FATAL_ERRORS:
                raise
            except ThreadsRateLimitError as exc:
                self._warn(exc.user_message)
                log_threads.warning("stopping keyword search on rate limit", keyword=kw)
                break
            except ThreadsAPIError as exc:
                self._warn(f"Keyword '{kw}': {exc.user_message}")
                continue
            cache_set(self.db, key, posts, self.cfg.cache.posts_ttl_hours)
            out[kw] = posts
        return out

    def _upsert_creator(self, username: str) -> Creator:
        creator = self.db.scalar(select(Creator).where(Creator.username == username))
        if creator is None:
            creator = Creator(
                username=username,
                profile_url=f"https://www.threads.net/@{username}",
                first_seen=utcnow(),
            )
            self.db.add(creator)
        creator.last_seen = utcnow()
        return creator

    def _upsert_post(self, creator: Creator, raw: dict, source: str, keywords: set[str]) -> Post:
        pid = str(raw["id"])
        post = self.db.scalar(select(Post).where(Post.threads_post_id == pid))
        if post is None:
            post = Post(threads_post_id=pid, creator=creator)
            self.db.add(post)
        post.text = raw.get("text")
        post.permalink = raw.get("permalink")
        post.timestamp = parse_threads_timestamp(raw.get("timestamp"))
        post.media_type = raw.get("media_type")
        post.media_url = raw.get("media_url")
        post.thumbnail_url = raw.get("thumbnail_url")
        post.has_replies = raw.get("has_replies")
        post.source = post.source if post.source == "keyword_search" else source
        if keywords:
            post.matched_keywords = sorted(set(post.matched_keywords or []) | keywords)
        post.fetched_at = utcnow()
        return post

    # ------------------------------------------------- profile prefetching
    async def _fetch_profile(self, username: str) -> dict | None:
        """profile_lookup via the AudienceProvider, with TTL cache.

        Returns the cached dict, or None when lookups are disabled/blocked.
        """
        if not self.cfg.search.lookup_profiles:
            return None
        key = f"profile:{username}"
        cached = cache_get(self.db, key)
        if cached is not None:
            return cached
        if self._profile_calls_blocked or self._lookup_denied:
            return None
        try:
            result = await self.deps.audience.get_audience(username)
        except ThreadsRateLimitError as exc:
            self._block_profile_calls(exc)
            return None
        cached = {
            "status": result.status,
            "follower_count": result.follower_count,
            "source": result.source,
            "profile": result.profile,
        }
        if result.status == "permission_denied":
            self._lookup_denied = True
            self._warn(
                "profile_lookup is not permitted for this app (threads_profile_discovery). "
                "Follower counts and bios are unavailable."
            )
        if result.status != "error":
            cache_set(self.db, key, cached, self.cfg.cache.profile_ttl_hours)
        return cached

    async def _fetch_profile_posts(self, username: str, profile: dict | None) -> list[dict] | None:
        if not self.cfg.search.fetch_profile_posts:
            return None
        if profile and profile.get("status") in ("permission_denied", "not_found"):
            return None
        key = f"profile_posts:{username}"
        cached = cache_get(self.db, key)
        if cached is not None:
            return cached
        if self._profile_calls_blocked or self._posts_denied:
            return None
        since = int((utcnow() - timedelta(days=90)).timestamp())
        try:
            posts = await self.deps.client.profile_posts(username, since=since)
        except AUTH_ERRORS:
            raise
        except ThreadsRateLimitError as exc:
            self._block_profile_calls(exc)
            return None
        except ThreadsPermissionError as exc:
            # App-wide permission problem: stop asking for every creator.
            if exc.code in PERMISSION_CODES:
                self._posts_denied = True
                self._warn(
                    "profile_posts is not permitted; activity uses keyword-search posts only (lower bound)."
                )
            return None
        except ThreadsAPIError as exc:
            log_threads.warning("profile_posts failed", username=username, error=type(exc).__name__)
            return None
        cache_set(self.db, key, posts, self.cfg.cache.posts_ttl_hours)
        return posts

    def _block_profile_calls(self, exc: ThreadsRateLimitError) -> None:
        if not self._profile_calls_blocked:
            self._profile_calls_blocked = True
            log_threads.warning("rate limited: no more profile calls this job")
            self._warn(exc.user_message + " Remaining creators were analysed with cached/search data only.")

    async def _prefetch_profiles(self, job: SearchJob, usernames: list[str]) -> dict[str, Prefetched]:
        """Fetch profile + recent posts for all candidates with bounded concurrency.

        DB access here is synchronous and never spans an ``await``, so the
        shared session is safe across these coroutines.
        """
        sem = asyncio.Semaphore(PREFETCH_CONCURRENCY)
        out: dict[str, Prefetched] = {}

        async def one(username: str) -> None:
            async with sem:
                profile = await self._fetch_profile(username)
                posts = await self._fetch_profile_posts(username, profile)
                out[username] = Prefetched(profile, posts)
                self._progress(job, profiles_done=len(out))

        try:
            async with asyncio.TaskGroup() as tg:
                for u in usernames:
                    tg.create_task(one(u))
        except BaseExceptionGroup as eg:  # surface the first real error (e.g. 401)
            raise eg.exceptions[0] from None
        return out

    def _apply_profile(self, creator: Creator, cached: dict | None) -> None:
        if cached is None:
            return
        creator.profile_lookup_status = cached["status"]
        creator.profile_checked_at = utcnow()
        creator.follower_count = cached["follower_count"]
        creator.follower_source = cached["source"]
        creator.follower_last_checked = utcnow()
        profile = cached.get("profile") or {}
        if profile:
            creator.display_name = profile.get("name") or creator.display_name
            creator.bio = profile.get("biography")
            creator.profile_picture_url = profile.get("profile_picture_url")
            creator.is_verified = profile.get("is_verified")
            for field, key2 in [
                ("profile_likes_count", "likes_count"),
                ("profile_replies_count", "replies_count"),
                ("profile_reposts_count", "reposts_count"),
                ("profile_quotes_count", "quotes_count"),
                ("profile_views_count", "views_count"),
            ]:
                v = profile.get(key2)
                setattr(creator, field, v if isinstance(v, int) and not isinstance(v, bool) else None)

    async def _embed_posts(self, posts: list[Post]) -> list[tuple[Post, np.ndarray]]:
        model = self.deps.embedder.model_name
        ttl = timedelta(hours=self.cfg.cache.embedding_ttl_hours)
        ready: list[tuple[Post, np.ndarray]] = []
        todo: list[Post] = []
        for p in posts:
            vec = from_bytes(p.image_embedding)
            if (
                vec is not None
                and p.embedding_model == model
                and p.embedded_at
                and utcnow() - to_aware(p.embedded_at) < ttl
            ):
                ready.append((p, vec))
            else:
                todo.append(p)
        if not todo:
            return ready
        urls = [p.media_url if p.media_type in IMAGE_MEDIA_TYPES else p.thumbnail_url for p in todo]
        blobs = await self.deps.fetcher.fetch_many([u or "" for u in urls])
        pairs = [(p, b) for p, b in zip(todo, blobs) if b]
        if not pairs:
            return ready
        log_embed.info("processing images", count=len(pairs))
        try:
            vecs = await asyncio.to_thread(self.deps.embedder.embed_images, [b for _, b in pairs])
        except Exception as exc:  # corrupt image in batch -> fall back one by one
            log_embed.warning("batch embedding failed, retrying individually", error=type(exc).__name__)
            vecs_list = []
            ok_pairs = []
            for p, b in pairs:
                try:
                    vecs_list.append((await asyncio.to_thread(self.deps.embedder.embed_images, [b]))[0])
                    ok_pairs.append((p, b))
                except Exception:
                    continue
            pairs = ok_pairs
            vecs = np.stack(vecs_list) if vecs_list else np.zeros((0, 1))
        for (p, _), v in zip(pairs, vecs):
            p.image_embedding = to_bytes(v)
            p.embedding_model = model
            p.embedded_at = utcnow()
            ready.append((p, v))
        self.db.commit()
        return ready

    # ------------------------------------------------------------------ run
    async def run(self, job: SearchJob) -> None:
        cfg = self.cfg
        filters = job.filters or {}
        keywords = [k for k in job.keywords if k.strip()]
        ref = self.db.get(ReferenceSet, job.reference_set_id) if job.reference_set_id else None
        ref_centroid = from_bytes(ref.centroid) if ref else None
        if ref is not None and ref.embedding_model != self.deps.embedder.model_name:
            raise ValueError(
                "Reference set was embedded with a different model; re-upload the reference images."
            )
        if ref_centroid is None:
            self._warn("No reference images: visual similarity is not scored.")

        self._progress(job, stage="keyword_search", keywords_total=len(keywords))
        by_kw = await self._keyword_search(keywords, filters)
        creators = dedupe_creators(by_kw)
        candidates = rank_candidates(creators, cfg.search.max_results * 2)
        log_threads.info(
            "deduplicated",
            posts=sum(len(v) for v in by_kw.values()),
            unique_creators=len(creators),
            analysing=len(candidates),
        )
        self._progress(job, creators_found=len(creators))

        ignored = set(
            self.db.scalars(
                select(Creator.username).where(
                    Creator.status == "ignored", Creator.username.in_([c.username for c in candidates])
                )
            ).all()
        )
        candidates = [c for c in candidates if c.username not in ignored]
        self._progress(job, stage="profiles", creators_total=len(candidates), profiles_done=0)
        prefetched = await self._prefetch_profiles(job, [c.username for c in candidates])

        self._progress(job, stage="analysing", creators_done=0)
        results: list[SearchResult] = []
        for i, cand in enumerate(candidates, 1):
            res = await self._analyse(job, cand, keywords, filters, ref_centroid, prefetched.get(cand.username))
            if res is not None:
                results.append(res)
            self._progress(job, creators_done=i)

        results.sort(key=lambda r: r.total_score, reverse=True)
        for r in results[: cfg.search.max_results]:
            self.db.add(r)
        self.db.commit()
        purge_expired(self.db, cfg.cache.embedding_ttl_hours)
        self._progress(job, stage="done", results=min(len(results), cfg.search.max_results))

    async def _analyse(
        self,
        job: SearchJob,
        cand: CandidateCreator,
        keywords: list[str],
        filters: dict,
        ref_centroid: np.ndarray | None,
        pre: Prefetched | None = None,
    ) -> SearchResult | None:
        cfg = self.cfg
        creator = self._upsert_creator(cand.username)
        if creator.status == "ignored":
            return None
        search_posts = [
            self._upsert_post(creator, raw, "keyword_search", cand.post_keywords.get(pid, set()))
            for pid, raw in cand.posts.items()
        ]
        self.db.flush()
        pre = pre or Prefetched(None, None)
        self._apply_profile(creator, pre.profile)

        profile_raw = pre.posts
        if profile_raw is not None:
            for raw in profile_raw:
                if raw.get("id"):
                    self._upsert_post(creator, raw, "profile_posts", set())
            timestamps = [parse_threads_timestamp(r.get("timestamp")) for r in profile_raw]
            timestamps += [p.timestamp for p in search_posts]
            creator.activity_source = "profile_posts"
        else:
            timestamps = [p.timestamp for p in search_posts]
            creator.activity_source = "keyword_search_sample"
        self.db.flush()

        counts = count_activity(timestamps)
        creator.posts_7d, creator.posts_30d, creator.posts_90d = (
            counts.posts_7d,
            counts.posts_30d,
            counts.posts_90d,
        )
        creator.last_post_at = counts.last_post_at
        act = activity_score(counts, cfg.activity)

        all_posts = self.db.scalars(
            select(Post)
            .where(Post.creator_id == creator.id)
            .order_by(Post.timestamp.desc())
            .limit(MAX_POSTS_PER_CREATOR_ANALYSED)
        ).all()
        texts = [creator.bio] + [p.text for p in all_posts]
        sig = detect_signals(texts)
        creator.creator_signal = sig.creator_level
        creator.monetization_signal = sig.monetization
        creator.signal_terms = sig.terms
        relevance, matched = keyword_relevance(keywords, texts, cand.keywords)

        # Visual similarity over the creator's image posts.
        vis = None
        best_url = None
        sim = aggregate_creator_similarity([])
        if ref_centroid is not None:
            image_posts = [
                p
                for p in all_posts
                if (p.media_type in IMAGE_MEDIA_TYPES and p.media_url)
                or (p.media_type == "VIDEO" and p.thumbnail_url)
            ]
            # Prefer posts that matched the search, then the most recent ones.
            image_posts.sort(
                key=lambda p: (
                    p.source != "keyword_search",
                    -(to_aware(p.timestamp).timestamp() if p.timestamp else 0),
                )
            )
            embedded = await self._embed_posts(image_posts[: cfg.search.max_images_per_creator])
            scores = [
                cosine_to_score(
                    cosine(ref_centroid, v), cfg.similarity.cosine_floor, cfg.similarity.cosine_ceiling
                )
                for _, v in embedded
            ]
            sim = aggregate_creator_similarity(
                scores,
                best_weight=cfg.similarity.best_weight,
                top_k_weight=cfg.similarity.top_k_weight,
                top_k=cfg.similarity.top_k,
            )
            vis = sim.score
            if sim.best_index is not None:
                bp = embedded[sim.best_index][0]
                best_url = bp.media_url if bp.media_type in IMAGE_MEDIA_TYPES else bp.thumbnail_url

        eng, eng_source = engagement_score(
            post_likes=[p.likes for p in all_posts],
            post_replies=[p.replies for p in all_posts],
            profile_interactions={
                "likes": creator.profile_likes_count,
                "replies": creator.profile_replies_count,
                "reposts": creator.profile_reposts_count,
                "quotes": creator.profile_quotes_count,
            },
        )
        aud = audience_score(creator.follower_count)
        components = {
            "visual_similarity": vis,
            "activity": act,
            "engagement": eng,
            "creator_signal": sig.creator_score,
            "keyword_relevance": relevance,
            "audience": aud,
        }
        total, breakdown = total_score(components, cfg.weights)
        breakdown["engagement_source"] = eng_source
        breakdown["activity_source"] = creator.activity_source

        passes, flags = apply_filters(
            FilterInput(
                posts_7d=counts.posts_7d,
                posts_30d=counts.posts_30d,
                posts_90d=counts.posts_90d,
                activity_is_lower_bound=creator.activity_source != "profile_posts",
                follower_count=creator.follower_count,
                replies=creator.profile_replies_count,
                likes=creator.profile_likes_count,
            ),
            filters,
        )
        log_score.info(
            "",
            creator=f"@{creator.username}",
            similarity=f"{(vis or 0) / 100:.2f}" if vis is not None else "n/a",
            activity=act,
            total=total,
            passes=passes,
        )
        if not passes:
            return None

        latest = max(
            (p for p in search_posts if p.timestamp), key=lambda p: to_aware(p.timestamp), default=None
        )
        return SearchResult(
            search_job_id=job.id,
            creator_id=creator.id,
            visual_similarity=vis,
            best_image_similarity=sim.best,
            top_k_avg_similarity=sim.top_k_avg,
            images_analyzed=sim.images_analyzed,
            activity_score=act,
            engagement_score=eng,
            creator_signal=sig.creator_score,
            keyword_relevance=relevance,
            audience_score=aud,
            total_score=total,
            score_breakdown=breakdown,
            matched_keywords=matched,
            latest_post_id=latest.id if latest else None,
            best_image_url=best_url,
            filter_flags=flags,
        )


async def run_search_job(job_id: int, session_factory, deps_factory) -> None:
    """Entry point used by the API background task."""
    from .app_config import load_config

    db: Session = session_factory()
    job = db.get(SearchJob, job_id)
    if job is None:
        db.close()
        return
    cfg = load_config(db)
    job.status = "running"
    db.commit()
    log_job.info("search job started", job=job_id, keywords=",".join(job.keywords))
    pipeline = None
    try:
        deps = await deps_factory(db)
        pipeline = SearchPipeline(db, deps, cfg)
        await pipeline.run(job)
        job.status = "completed"
    except ThreadsAPIError as exc:
        db.rollback()
        job.status = "failed"
        job.error = exc.user_message
        log_job.error("search job failed", job=job_id, error=type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        db.rollback()
        job.status = "failed"
        job.error = str(exc) or type(exc).__name__
        log_job.error("search job failed", job=job_id, error=type(exc).__name__, detail=str(exc)[:200])
    finally:
        job.warnings = pipeline.warnings if pipeline else []
        job.completed_at = utcnow()
        db.commit()
        db.close()
        log_job.info("search job finished", job=job_id, status=job.status)


__all__ = ["PipelineDeps", "SearchPipeline", "run_search_job", "OfficialThreadsAudienceProvider"]
