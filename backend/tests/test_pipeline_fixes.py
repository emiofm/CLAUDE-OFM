"""Regression tests for pipeline robustness fixes."""
from datetime import timedelta

import httpx
import pytest

from app.db import SessionLocal
from app.models import SearchJob, ThreadsConnection
from app.services.app_config import AppConfig
from app.services.audience import OfficialThreadsAudienceProvider
from app.services.embeddings import ColorHistogramEmbedder
from app.services.images import ImageFetcher
from app.services.pipeline import PipelineDeps, SearchPipeline
from app.threads.errors import ThreadsRateLimitError
from app.threads.oauth import needs_refresh, save_connection
from app.config import get_settings
from app.utils import utcnow
from tests.fake_threads import FakeThreadsAPI, err, post
from tests.test_threads_client import make_client


def _pipeline(api: FakeThreadsAPI, db):
    tc = make_client(api)
    deps = PipelineDeps(
        client=tc,
        embedder=ColorHistogramEmbedder(),
        fetcher=ImageFetcher(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
        audience=OfficialThreadsAudienceProvider(tc),
    )
    return SearchPipeline(db, deps, AppConfig())


def _job(db, keywords):
    job = SearchJob(keywords=keywords, filters={})
    db.add(job)
    db.commit()
    return job


def _count(api, suffix):
    return sum(1 for r in api.requests if r.url.path.endswith(suffix))


async def test_rate_limit_on_profile_lookup_stops_further_profile_calls():
    api = FakeThreadsAPI(page_size_cap=100)
    api.search_results["kw"] = [post(i, f"user{i}") for i in range(10)]

    orig = api.handler
    def handler(request):
        if request.url.path.endswith("/profile_lookup"):
            api.requests.append(request)
            return err(429)
        return orig(request)
    api.handler = handler

    db = SessionLocal()
    pipe = _pipeline(api, db)
    job = _job(db, ["kw"])
    await pipe.run(job)
    # Without the fix every creator triggered another 429; now calls stop quickly.
    assert _count(api, "/profile_lookup") <= 4  # at most the in-flight concurrent batch
    assert _count(api, "/profile_posts") == 0
    assert any("rate limit" in w.lower() for w in pipe.warnings)
    db.close()


async def test_app_wide_profile_posts_denial_is_not_retried_per_creator():
    api = FakeThreadsAPI(page_size_cap=100)
    api.search_results["kw"] = [post(i, f"user{i}") for i in range(12)]
    for i in range(12):
        api.profiles[f"user{i}"] = {"username": f"user{i}"}
    db = SessionLocal()
    pipe = _pipeline(api, db)
    await pipe.run(_job(db, ["kw"]))
    assert _count(api, "/profile_lookup") == 12
    assert _count(api, "/profile_posts") <= 4  # stops after the first code-10 denial
    db.close()


async def test_audience_provider_propagates_rate_limit():
    api = FakeThreadsAPI()
    api.forced = [err(429)]
    with pytest.raises(ThreadsRateLimitError):
        await OfficialThreadsAudienceProvider(make_client(api)).get_audience("x")


async def test_audience_result_carries_profile_without_shared_state():
    api = FakeThreadsAPI()
    api.profiles["a"] = {"username": "a", "name": "A", "follower_count": 5}
    api.profiles["b"] = {"username": "b", "name": "B"}
    prov = OfficialThreadsAudienceProvider(make_client(api))
    import asyncio

    ra, rb = await asyncio.gather(prov.get_audience("a"), prov.get_audience("b"))
    assert ra.profile["name"] == "A" and rb.profile["name"] == "B"
    assert not hasattr(prov, "last_profile")


def test_reconnecting_resets_refresh_clock():
    db = SessionLocal()
    settings = get_settings()
    conn = save_connection(db, settings, access_token="t1", expires_in=86400, token_type="bearer")
    conn.issued_at = utcnow() - timedelta(days=59)
    db.commit()
    conn = save_connection(db, settings, access_token="t2", expires_in=86400, token_type="bearer")
    assert utcnow() - conn.issued_at < timedelta(minutes=1)
    # fresh token (< 24h old) must not be refreshed even though it expires soon
    assert needs_refresh(conn) is False
    assert db.query(ThreadsConnection).count() == 1
    db.close()
