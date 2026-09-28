import pytest

from app.threads.client import POST_FIELDS, ThreadsClient
from app.threads.errors import ThreadsNotConnectedError
from tests.fake_threads import FakeThreadsAPI, post


def make_client(api, token="tok-123", **kw):
    async def nosleep(_):
        return None

    return ThreadsClient(lambda: token, graph_url="https://graph.test/v1.0", transport=api.transport(), sleep=nosleep, **kw)


async def test_keyword_search_sends_documented_params_and_bearer_header():
    api = FakeThreadsAPI()
    api.search_results["brunette"] = [post(1, "alice", "hi")]
    client = make_client(api)
    out = await client.keyword_search("brunette", search_type="recent", media_type="image", page_size=10)
    assert out[0]["username"] == "alice"
    req = api.requests[0]
    assert req.url.path == "/v1.0/keyword_search"
    params = dict(req.url.params)
    assert params["q"] == "brunette"
    assert params["search_type"] == "RECENT"
    assert params["search_mode"] == "KEYWORD"
    assert params["media_type"] == "IMAGE"
    assert params["fields"] == POST_FIELDS
    assert params["limit"] == "10"
    # Token is sent in the Authorization header, never in the URL.
    assert req.headers["Authorization"] == "Bearer tok-123"
    assert "tok-123" not in str(req.url)


async def test_keyword_search_validates_inputs():
    client = make_client(FakeThreadsAPI())
    with pytest.raises(ValueError):
        await client.keyword_search("  ")
    with pytest.raises(ValueError):
        await client.keyword_search("x", search_type="LATEST")
    with pytest.raises(ValueError):
        await client.keyword_search("x", media_type="CAROUSEL")


async def test_limit_is_capped_and_since_clamped():
    api = FakeThreadsAPI()
    client = make_client(api)
    await client.keyword_search("x", page_size=500, since=5)
    params = dict(api.requests[0].url.params)
    assert params["limit"] == "100"
    assert params["since"] == "1688540400"


async def test_profile_lookup_maps_documented_fields_only():
    api = FakeThreadsAPI()
    api.profiles["alice"] = {
        "username": "alice", "name": "Alice", "biography": "creator", "follower_count": 4200,
        "profile_picture_url": "https://cdn/p.jpg", "is_verified": False, "likes_count": 10,
        "unexpected_field": "ignored",
    }
    client = make_client(api)
    prof = await client.profile_lookup("@alice")
    assert dict(api.requests[0].url.params) == {"username": "alice"}
    assert prof["follower_count"] == 4200
    assert prof["replies_count"] is None  # absent -> None, not 0
    assert "unexpected_field" not in prof


async def test_profile_lookup_not_found_returns_none():
    client = make_client(FakeThreadsAPI())
    assert await client.profile_lookup("ghost") is None


async def test_missing_token_raises_not_connected():
    client = make_client(FakeThreadsAPI(), token=None)
    with pytest.raises(ThreadsNotConnectedError) as ei:
        await client.me()
    assert "Connect Threads" in ei.value.user_message
