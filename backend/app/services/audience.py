"""Audience (follower count) providers.

The application never invents follower counts. A provider returns an int only
when its source legitimately reports one, and ``None`` otherwise.

To add a compliant third-party source, subclass ``AudienceProvider`` and
return it from ``default_deps_factory`` in ``app/deps.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..logging_conf import get_logger
from ..threads.client import ThreadsClient
from ..threads.errors import (
    ThreadsAPIError,
    ThreadsAuthError,
    ThreadsNotConnectedError,
    ThreadsPermissionError,
    ThreadsRateLimitError,
)

log = get_logger("AUDIENCE")


@dataclass
class AudienceResult:
    follower_count: int | None
    source: str | None
    status: str  # ok / unavailable / not_found / permission_denied / error
    # Raw public profile fields returned by the source (if any).
    profile: dict | None = field(default=None)


class AudienceProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def get_follower_count(self, username: str) -> int | None:
        """Return the follower count, or None if the source cannot provide it."""

    async def get_audience(self, username: str) -> AudienceResult:
        count = await self.get_follower_count(username)
        return AudienceResult(count, self.name if count is not None else None,
                              "ok" if count is not None else "unavailable")


class NullAudienceProvider(AudienceProvider):
    """Used when no source is configured: always unavailable."""

    name = "none"

    async def get_follower_count(self, username: str) -> int | None:
        return None


class OfficialThreadsAudienceProvider(AudienceProvider):
    """Reads ``follower_count`` from the official ``profile_lookup`` endpoint.

    This requires the ``threads_profile_discovery`` permission (App Review).
    Meta only returns data for public profiles it makes discoverable; when the
    field is missing or the call is not permitted, this returns None.
    """

    name = "threads_profile_lookup"

    def __init__(self, client: ThreadsClient):
        self.client = client

    async def get_follower_count(self, username: str) -> int | None:
        return (await self.get_audience(username)).follower_count

    async def get_audience(self, username: str) -> AudienceResult:
        """Rate-limit and auth errors propagate so callers stop calling the API."""
        try:
            profile = await self.client.profile_lookup(username)
        except (ThreadsRateLimitError, ThreadsAuthError, ThreadsNotConnectedError):
            raise
        except ThreadsPermissionError:
            log.warning("profile_lookup not permitted", username=username)
            return AudienceResult(None, None, "permission_denied")
        except ThreadsAPIError as exc:
            log.warning("profile_lookup failed", username=username, error=type(exc).__name__)
            return AudienceResult(None, None, "error")
        if profile is None:
            return AudienceResult(None, None, "not_found")
        count = profile.get("follower_count")
        if isinstance(count, bool) or not isinstance(count, int):
            return AudienceResult(None, None, "unavailable", profile)
        return AudienceResult(count, self.name, "ok", profile)
