"""End-to-end API flow with a fake Threads API and deterministic embedder."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.audience import OfficialThreadsAudienceProvider
from app.services.embeddings import ColorHistogramEmbedder
from app.services.images import ImageFetcher
from app.services.pipeline import PipelineDeps
from tests.conftest import BLUE, BROWN, make_image
from tests.fake_threads import FakeThreadsAPI, err, post
from tests.test_threads_client import make_client

IMAGES = {
    **{f"https://cdn.test/a{i}.jpg": make_image(BROWN, seed=100 + i) for i in range(4)},
    **{f"https://cdn.test/b{i}.jpg": make_image(BLUE, seed=200 + i) for i in range(4)},
}


def cdn_handler(request: httpx.Request) -> httpx.Response:
    data = IMAGES.get(str(request.url))
    if data is None:
        return httpx.Response(404)
    return httpx.Response(200, content=data, headers={"content-type": "image/png"})


@pytest.fixture
def api():
    fake = FakeThreadsAPI(page_size_cap=2)
    fake.search_results["brunette"] = [
        post("a0", "alice", "brunette content creator, link in bio", 1, media_url="https://cdn.test/a0.jpg"),
        post("a1", "alice", "morning coffee", 3, media_url="https://cdn.test/a1.jpg"),
        post("b0", "bob", "brunette at the beach", 2, media_url="https://cdn.test/b0.jpg"),
    ]
    fake.search_results["lifestyle creator"] = [
        post("a2", "alice", "lifestyle creator life", 5, media_url="https://cdn.test/a2.jpg"),
        post("b1", "bob", "lifestyle creator", 40, media_url="https://cdn.test/b1.jpg"),
    ]
    fake.profiles["alice"] = {"username": "alice", "name": "Alice", "biography": "exclusive content ✨",
                              "follower_count": 42300, "profile_picture_url": "https://cdn.test/pa.jpg",
                              "likes_count": 900, "replies_count": 120}
    fake.profiles["bob"] = {"username": "bob", "name": "Bob", "biography": "photographer"}  # no follower_count
    fake.profile_posts["alice"] = [post(f"ap{i}", "alice", "", i * 2, media_type="TEXT") for i in range(12)]
    return fake


@pytest.fixture
def client(api):
    app = create_app()
    embedder = ColorHistogramEmbedder()

    async def deps_factory(db):
        tc = make_client(api)
        return PipelineDeps(
            client=tc,
            embedder=embedder,
            fetcher=ImageFetcher(transport=httpx.MockTransport(cdn_handler)),
            audience=OfficialThreadsAudienceProvider(tc),
        )

    app.state.deps_factory = deps_factory
    app.state.client_factory = lambda db: make_client(api)
    app.state.embedder_factory = lambda: embedder
    with TestClient(app) as c:
        yield c


def upload_refs(client, n=3, color=BROWN):
    files = [("files", (f"r{i}.png", make_image(color, seed=i), "image/png")) for i in range(n)]
    r = client.post("/api/reference-sets", data={"name": "Model A"}, files=files)
    return r


def test_reference_upload_limits(client):
    assert upload_refs(client, n=2).status_code == 400
    r = upload_refs(client, n=3)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["images"]) == 3 and body["embedding_model"] == "debug-color-histogram"
    img = client.get(body["images"][0]["url"])
    assert img.status_code == 200
    bad = client.post("/api/reference-sets", files=[("files", (f"x{i}.txt", b"nope", "text/plain")) for i in range(3)])
    assert bad.status_code == 400


def test_full_search_flow(client, api):
    ref = upload_refs(client).json()
    r = client.post("/api/search", json={
        "reference_set_id": ref["id"],
        "keywords": ["brunette", "lifestyle creator", "Brunette"],
        "filters": {"min_followers": 20000},
    })
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["keywords"] == ["brunette", "lifestyle creator"]  # de-duplicated

    status = client.get(f"/api/search/{job['id']}").json()
    assert status["status"] == "completed", status

    res = client.get(f"/api/search/{job['id']}/results").json()["results"]
    names = [x["creator"]["username"] for x in res]
    assert names == ["alice", "bob"]  # one entry per creator, alice best match
    alice, bob = res
    assert alice["visual_similarity"] > bob["visual_similarity"]
    assert alice["creator"]["followers"] == {"value": 42300, "available": True,
                                             "source": "threads_profile_lookup", "note": None}
    # profile_posts is paginated (4 pages x 2 items in the fake) + 3 search hits
    assert alice["creator"]["posts_30d"]["value"] == 11
    assert alice["creator"]["posts_30d"]["note"] is None
    assert alice["creator"]["monetization_label"] == "Possible monetization signal"
    assert set(alice["matched_keywords"]) == {"brunette", "lifestyle creator"}
    assert alice["engagement_score"] is not None
    # Bob: no follower_count from API -> unavailable, flagged, never invented.
    assert bob["creator"]["followers"]["value"] is None
    assert bob["creator"]["followers"]["note"] == "Follower count unavailable from official Threads API"
    assert "followers_unavailable" in bob["filter_flags"]
    assert bob["engagement_score"] is None
    assert "engagement" in bob["score_breakdown"]["unavailable"]
    # Bob's profile_posts is forbidden -> activity is a lower bound from search hits
    assert bob["creator"]["posts_30d"]["note"].startswith("Lower bound")

    # sorting
    newest = client.get(f"/api/search/{job['id']}/results?sort=newest").json()["results"]
    assert newest[0]["creator"]["username"] == "alice"

    # save / ignore
    cid = bob["creator"]["id"]
    assert client.post(f"/api/creators/{alice['creator']['id']}/save").json()["status"] == "saved"
    client.post(f"/api/creators/{cid}/ignore")
    res2 = client.get(f"/api/search/{job['id']}/results").json()["results"]
    assert [x["creator"]["username"] for x in res2] == ["alice"]
    saved = client.get("/api/creators?status=saved").json()
    assert [s["creator"]["username"] for s in saved] == ["alice"]

    # second search uses cached keyword results and embeddings (no extra keyword_search calls)
    n_kw = sum(1 for q in api.requests if q.url.path.endswith("/keyword_search"))
    client.post("/api/search", json={"reference_set_id": ref["id"], "keywords": ["brunette"]})
    n_kw2 = sum(1 for q in api.requests if q.url.path.endswith("/keyword_search"))
    assert n_kw2 == n_kw


def test_strict_follower_filter_excludes_unknown(client):
    ref = upload_refs(client).json()
    job = client.post("/api/search", json={"reference_set_id": ref["id"], "keywords": ["brunette"],
                                           "filters": {"min_followers": 1000, "strict_unknown_metrics": True}}).json()
    res = client.get(f"/api/search/{job['id']}/results").json()["results"]
    assert [x["creator"]["username"] for x in res] == ["alice"]


def test_search_without_reference_images_warns(client):
    job = client.post("/api/search", json={"keywords": ["brunette"]}).json()
    j = client.get(f"/api/search/{job['id']}").json()
    assert j["status"] == "completed"
    assert any("visual similarity" in w for w in j["warnings"])
    res = client.get(f"/api/search/{job['id']}/results").json()["results"]
    assert all(r["visual_similarity"] is None for r in res)


@pytest.mark.parametrize("status,code,needle", [
    (401, 190, "Reconnect Threads"),
    (403, 10, "missing a required permission"),
])
def test_search_job_surfaces_auth_errors(client, api, status, code, needle):
    api.forced = [err(status, code)]
    job = client.post("/api/search", json={"keywords": ["brunette"]}).json()
    j = client.get(f"/api/search/{job['id']}").json()
    assert j["status"] == "failed"
    assert needle in j["error"]


def test_search_job_rate_limit_becomes_warning(client, api):
    api.forced = [err(429)]
    job = client.post("/api/search", json={"keywords": ["brunette"]}).json()
    j = client.get(f"/api/search/{job['id']}").json()
    assert j["status"] == "completed"
    assert any("rate limit" in w.lower() for w in j["warnings"])


def test_validation(client):
    assert client.post("/api/search", json={"keywords": []}).status_code == 422
    assert client.post("/api/search", json={"keywords": ["  "]}).status_code == 422
    assert client.post("/api/search", json={"keywords": ["x"], "reference_set_id": 999}).status_code == 404
    assert client.post("/api/search", json={"keywords": ["x"], "filters": {"min_followers": 10, "max_followers": 5}}).status_code == 400


def test_settings_roundtrip_and_test_endpoints(client, api):
    s = client.get("/api/settings").json()
    assert s["config"]["weights"]["visual_similarity"] == 45
    assert s["threads"]["connected"] is False
    assert "super-secret-value" not in str(s)
    assert s["data_availability"]["unavailable"]
    cfg = s["config"]
    cfg["weights"]["visual_similarity"] = 60
    assert client.put("/api/settings", json=cfg).json()["config"]["weights"]["visual_similarity"] == 60
    cfg["similarity"]["cosine_floor"] = 0.99
    assert client.put("/api/settings", json=cfg).status_code == 422
    assert client.post("/api/settings/test-connection").json() == {"ok": True, "username": "me_account", "id": "1"}
    t = client.post("/api/settings/test-keyword-search", json={"q": "brunette"}).json()
    assert t["ok"] and t["count"] == 2  # a single page only
    api.forced = [err(401, 190)]
    bad = client.post("/api/settings/test-connection").json()
    assert bad["ok"] is False and bad["status_code"] == 401


def test_oauth_flow(client):
    r = client.get("/auth/threads", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://threads.net/oauth/authorize?")
    assert "client_id=123" in loc and "threads_keyword_search" in loc
    assert "super-secret-value" not in loc
    state = r.cookies.get("threads_oauth_state")
    assert state and f"state={state}" in loc

    def meta(request: httpx.Request):
        path = request.url.path
        if path == "/oauth/access_token":
            assert b"client_secret=super-secret-value" in request.content
            return httpx.Response(200, json={"access_token": "SHORT", "user_id": 77})
        if path == "/access_token":
            assert request.url.params["grant_type"] == "th_exchange_token"
            return httpx.Response(200, json={"access_token": "LONG", "token_type": "bearer", "expires_in": 5184000})
        if path.endswith("/debug_token"):
            return httpx.Response(200, json={"data": {"scopes": ["threads_basic", "threads_keyword_search"]}})
        if path.endswith("/me"):
            assert request.headers["Authorization"] == "Bearer LONG"
            return httpx.Response(200, json={"id": "77", "username": "agency"})
        return httpx.Response(404)

    client.app.state.oauth_transport = httpx.MockTransport(meta)
    bad = client.get("/auth/threads/callback?code=abc&state=wrong", follow_redirects=False)
    assert "invalid_state" in bad.headers["location"]
    client.cookies.set("threads_oauth_state", state)
    ok = client.get(f"/auth/threads/callback?code=abc%23_&state={state}", follow_redirects=False)
    assert ok.headers["location"] == "http://frontend.test/settings?threads=connected"
    s = client.get("/api/settings").json()["threads"]
    assert s["connected"] and s["username"] == "agency" and s["token_source"] == "oauth"
    assert s["missing_scopes"] == ["threads_profile_discovery"]
    assert "LONG" not in str(s)
    assert client.post("/auth/threads/disconnect").json() == {"connected": False}
