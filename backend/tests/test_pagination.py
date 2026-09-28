import pytest

from app.threads.client import SlidingWindowBudget
from app.threads.errors import LocalBudgetExceededError
from tests.fake_threads import FakeThreadsAPI, post
from tests.test_threads_client import make_client


def seed(api, n, q="kw"):
    api.search_results[q] = [post(i, f"user{i}") for i in range(n)]


async def test_follows_after_cursor_until_exhausted():
    api = FakeThreadsAPI(page_size_cap=2)
    seed(api, 5)
    out = await make_client(api).keyword_search("kw", max_pages=10, max_items=100)
    assert [p["id"] for p in out] == ["0", "1", "2", "3", "4"]
    assert len(api.requests) == 3
    assert "after" not in api.requests[0].url.params
    assert api.requests[1].url.params["after"] == "2"
    assert api.requests[2].url.params["after"] == "4"


async def test_stops_at_max_pages():
    api = FakeThreadsAPI(page_size_cap=2)
    seed(api, 10)
    out = await make_client(api).keyword_search("kw", max_pages=2, max_items=100)
    assert len(out) == 4
    assert len(api.requests) == 2


async def test_stops_at_max_items():
    api = FakeThreadsAPI(page_size_cap=2)
    seed(api, 10)
    out = await make_client(api).keyword_search("kw", max_pages=10, max_items=3)
    assert len(out) == 3
    assert len(api.requests) == 2


async def test_empty_first_page():
    api = FakeThreadsAPI()
    assert await make_client(api).keyword_search("nothing") == []
    assert len(api.requests) == 1


async def test_repeated_cursor_does_not_loop_forever():
    import httpx

    api = FakeThreadsAPI()
    loop_page = {"data": [post(1, "a")], "paging": {"cursors": {"after": "SAME"}, "next": "x"}}
    api.forced = [httpx.Response(200, json=loop_page) for _ in range(5)]
    out = await make_client(api).keyword_search("kw", max_pages=5, max_items=100)
    assert len(api.requests) == 2
    assert len(out) == 2


async def test_each_page_consumes_local_budget_and_stops_when_exhausted():
    api = FakeThreadsAPI(page_size_cap=2)
    seed(api, 10)
    budget = SlidingWindowBudget(3)
    client = make_client(api, keyword_budget=budget)
    with pytest.raises(LocalBudgetExceededError):
        await client.keyword_search("kw", max_pages=10, max_items=100)
    assert len(api.requests) == 3
    assert budget.remaining == 0


def test_budget_window_expires():
    now = [0.0]
    b = SlidingWindowBudget(1, window_s=10, clock=lambda: now[0])
    b.consume()
    assert b.remaining == 0
    now[0] = 11
    assert b.remaining == 1


async def test_profile_posts_paginates():
    api = FakeThreadsAPI(page_size_cap=2)
    api.profile_posts["alice"] = [post(i, "alice") for i in range(5)]
    out = await make_client(api).profile_posts("alice", max_pages=10)
    assert len(out) == 5
    assert all(r.url.path.endswith("/profile_posts") for r in api.requests)
