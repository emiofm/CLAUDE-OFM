"""Fetch publicly available post images returned by the Threads API.

Images are downloaded into memory, embedded, and discarded. Only the
embedding vector is cached (with a TTL); third-party image bytes are never
written to disk.
"""
from __future__ import annotations

import asyncio

import httpx

from ..logging_conf import get_logger

log = get_logger("EMBEDDING")


class ImageFetcher:
    def __init__(
        self,
        *,
        max_bytes: int = 8 * 1024 * 1024,
        timeout_s: float = 15.0,
        concurrency: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.max_bytes = max_bytes
        self.timeout_s = timeout_s
        self._sem = asyncio.Semaphore(concurrency)
        self._transport = transport

    async def fetch(self, url: str) -> bytes | None:
        if not url.startswith("https://"):
            return None
        async with self._sem:
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout_s, transport=self._transport, follow_redirects=True
                ) as http:
                    async with http.stream("GET", url) as resp:
                        if resp.status_code != 200:
                            log.warning("image fetch failed", status=resp.status_code)
                            return None
                        ctype = resp.headers.get("content-type", "")
                        if not ctype.startswith("image/"):
                            return None
                        buf = bytearray()
                        async for chunk in resp.aiter_bytes():
                            buf.extend(chunk)
                            if len(buf) > self.max_bytes:
                                log.warning("image too large, skipped")
                                return None
                        return bytes(buf)
            except httpx.HTTPError as exc:
                log.warning("image fetch error", error=type(exc).__name__)
                return None

    async def fetch_many(self, urls: list[str]) -> list[bytes | None]:
        return await asyncio.gather(*(self.fetch(u) for u in urls))
