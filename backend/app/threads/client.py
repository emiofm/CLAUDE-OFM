"""Minimal, compliant client for the official Threads Graph API.

Only endpoints/fields verified against Meta's Threads API reference are used:

* ``GET /{version}/keyword_search``   (permission: threads_keyword_search)
    params: q, search_type (TOP|RECENT), search_mode (KEYWORD|TAG),
            media_type (TEXT|IMAGE|VIDEO), since, until, limit, before/after,
            author_username, fields
* ``GET /{version}/profile_lookup``   (permission: threads_profile_discovery)
    params: username (exact match). Returns username, name,
    profile_picture_url, biography, is_verified, follower_count, likes_count,
    quotes_count, replies_count, reposts_count, views_count.
* ``GET /{version}/profile_posts``    (permission: threads_profile_discovery)
    params: username, fields, since, until, limit, before/after
* ``GET /{version}/me``               (permission: threads_basic)

Pagination uses the ``paging.cursors.after`` cursor. The client never assumes
a single call returns everything, stops at configurable page/item caps and
honours HTTP 429 / Meta throttling codes instead of trying to evade them.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ..logging_conf import get_logger
from .errors import (
    LocalBudgetExceededError,
    ThreadsAPIError,
    ThreadsNotConnectedError,
    ThreadsRateLimitError,
    ThreadsServerError,
    error_from_response,
)

log = get_logger("THREADS")

POST_FIELDS = (
    "id,text,media_type,media_url,thumbnail_url,permalink,timestamp,"
    "username,has_replies,is_quote_post,is_reply"
)
PROFILE_LOOKUP_KEYS = (
    "username",
    "name",
    "profile_picture_url",
    "biography",
    "is_verified",
    "follower_count",
    "likes_count",
    "quotes_count",
    "replies_count",
    "reposts_count",
    "views_count",
)
SEARCH_TYPES = {"TOP", "RECENT"}
SEARCH_MODES = {"KEYWORD", "TAG"}
MEDIA_TYPES = {"TEXT", "IMAGE", "VIDEO"}
MAX_PAGE_LIMIT = 100
# Meta: since must be >= 1688540400 (Threads launch).
MIN_SINCE = 1688540400

TokenProvider = Callable[[], Awaitable[str | None]] | Callable[[], str | None]


class SlidingWindowBudget:
    """Local guard that keeps us under a request budget in a rolling window."""

    def __init__(self, max_requests: int, window_s: float = 24 * 3600, clock=time.monotonic):
        self.max_requests = max_requests
        self.window_s = window_s
        self._clock = clock
        self._hits: deque[float] = deque()

    def _trim(self) -> None:
        now = self._clock()
        while self._hits and now - self._hits[0] > self.window_s:
            self._hits.popleft()

    @property
    def remaining(self) -> int:
        self._trim()
        return max(0, self.max_requests - len(self._hits))

    def consume(self) -> None:
        self._trim()
        if len(self._hits) >= self.max_requests:
            raise LocalBudgetExceededError()
        self._hits.append(self._clock())


class ThreadsClient:
    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        graph_url: str = "https://graph.threads.net/v1.0",
        timeout_s: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        keyword_budget: SlidingWindowBudget | None = None,
        profile_budget: SlidingWindowBudget | None = None,
        max_retries: int = 2,
        max_retry_after_s: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._token_provider = token_provider
        self.graph_url = graph_url.rstrip("/")
        self._timeout = timeout_s
        self._transport = transport
        self.keyword_budget = keyword_budget
        self.profile_budget = profile_budget
        self.max_retries = max_retries
        self.max_retry_after_s = max_retry_after_s
        self._sleep = sleep

    # ------------------------------------------------------------------ core
    async def _token(self) -> str:
        tok = self._token_provider()
        if asyncio.iscoroutine(tok):
            tok = await tok
        if not tok:
            raise ThreadsNotConnectedError()
        return tok

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        token = await self._token()
        url = f"{self.graph_url}/{path.lstrip('/')}"
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        attempt = 0
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as http:
            while True:
                attempt += 1
                try:
                    resp = await http.get(
                        url, params=clean, headers={"Authorization": f"Bearer {token}"}
                    )
                except httpx.TransportError as exc:
                    if attempt <= self.max_retries:
                        await self._sleep(2 ** attempt)
                        continue
                    raise ThreadsServerError(f"network error: {type(exc).__name__}") from exc

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ThreadsAPIError("invalid JSON from Threads", status_code=200) from exc

                try:
                    body = resp.json()
                except ValueError:
                    body = None
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                err = error_from_response(resp.status_code, body, retry_after)
                log.warning(
                    "api error",
                    path=path,
                    status=resp.status_code,
                    meta_code=err.code,
                    error=type(err).__name__,
                )

                # Respect throttling: wait only when Meta tells us how long and
                # it is short; otherwise surface the error. Never hammer.
                if isinstance(err, ThreadsRateLimitError):
                    if (
                        attempt <= 1
                        and retry_after is not None
                        and retry_after <= self.max_retry_after_s
                    ):
                        log.info("rate limited, honouring Retry-After", seconds=retry_after)
                        await self._sleep(retry_after)
                        continue
                    raise err
                if isinstance(err, ThreadsServerError) and attempt <= self.max_retries:
                    await self._sleep(2 ** attempt)
                    continue
                raise err

    async def paginate(
        self,
        path: str,
        params: dict[str, Any],
        *,
        max_pages: int,
        max_items: int,
        before_each_page: Callable[[], None] | None = None,
    ) -> list[dict]:
        """Follow ``paging.cursors.after`` until exhausted or caps are reached."""
        items: list[dict] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for page in range(1, max_pages + 1):
            if before_each_page:
                before_each_page()
            page_params = dict(params)
            if cursor:
                page_params["after"] = cursor
            data = await self._get(path, page_params)
            batch = data.get("data") or []
            items.extend(batch)
            log.debug("page received", path=path, page=page, items=len(batch))
            if len(items) >= max_items or not batch:
                break
            paging = data.get("paging") or {}
            cursor = (paging.get("cursors") or {}).get("after") or paging.get("after")
            has_next = bool(paging.get("next")) or bool(cursor)
            if not cursor or not has_next or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
        return items[:max_items]

    # ------------------------------------------------------------- endpoints
    async def keyword_search(
        self,
        q: str,
        *,
        search_type: str = "TOP",
        search_mode: str = "KEYWORD",
        media_type: str | None = None,
        since: int | None = None,
        until: int | None = None,
        author_username: str | None = None,
        page_size: int = 50,
        max_pages: int = 3,
        max_items: int = 150,
    ) -> list[dict]:
        q = (q or "").strip()
        if not q:
            raise ValueError("keyword must not be empty")
        search_type = search_type.upper()
        search_mode = search_mode.upper()
        if search_type not in SEARCH_TYPES:
            raise ValueError(f"search_type must be one of {sorted(SEARCH_TYPES)}")
        if search_mode not in SEARCH_MODES:
            raise ValueError(f"search_mode must be one of {sorted(SEARCH_MODES)}")
        if media_type:
            media_type = media_type.upper()
            if media_type not in MEDIA_TYPES:
                raise ValueError(f"media_type must be one of {sorted(MEDIA_TYPES)}")
        if since is not None and since < MIN_SINCE:
            since = MIN_SINCE
        params = {
            "q": q,
            "search_type": search_type,
            "search_mode": search_mode,
            "media_type": media_type,
            "since": since,
            "until": until,
            "author_username": author_username.lstrip("@") if author_username else None,
            "limit": max(1, min(page_size, MAX_PAGE_LIMIT)),
            "fields": POST_FIELDS,
        }
        log.info("keyword search started", keyword=q, search_type=search_type)
        results = await self.paginate(
            "keyword_search",
            params,
            max_pages=max_pages,
            max_items=max_items,
            before_each_page=self.keyword_budget.consume if self.keyword_budget else None,
        )
        log.info("keyword search finished", keyword=q, results_received=len(results))
        return results

    async def profile_lookup(self, username: str) -> dict | None:
        """Public profile by exact username. Returns None if not found/not public."""
        from .errors import ThreadsNotFoundError

        username = username.lstrip("@").strip()
        if self.profile_budget:
            self.profile_budget.consume()
        try:
            data = await self._get("profile_lookup", {"username": username})
        except ThreadsNotFoundError:
            return None
        return {k: data.get(k) for k in PROFILE_LOOKUP_KEYS}

    async def profile_posts(
        self,
        username: str,
        *,
        since: int | None = None,
        page_size: int = 50,
        max_pages: int = 4,
        max_items: int = 200,
    ) -> list[dict]:
        params = {
            "username": username.lstrip("@"),
            "fields": POST_FIELDS,
            "since": max(since, MIN_SINCE) if since else None,
            "limit": max(1, min(page_size, MAX_PAGE_LIMIT)),
        }
        return await self.paginate(
            "profile_posts",
            params,
            max_pages=max_pages,
            max_items=max_items,
            before_each_page=self.profile_budget.consume if self.profile_budget else None,
        )

    async def me(self) -> dict:
        return await self._get(
            "me", {"fields": "id,username,name,threads_profile_picture_url,threads_biography"}
        )


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
