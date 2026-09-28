"""An in-memory fake of the Threads Graph API built on httpx.MockTransport."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx


def ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def post(pid, username, text="", days_ago=1.0, media_type="IMAGE", media_url=None):
    return {
        "id": str(pid),
        "username": username,
        "text": text,
        "timestamp": ts(days_ago),
        "media_type": media_type,
        "media_url": media_url or f"https://cdn.test/{pid}.jpg",
        "permalink": f"https://www.threads.net/@{username}/post/{pid}",
        "has_replies": False,
    }


class FakeThreadsAPI:
    def __init__(self, page_size_cap: int = 2):
        self.search_results: dict[str, list[dict]] = {}
        self.profiles: dict[str, dict] = {}
        self.profile_posts: dict[str, list[dict]] = {}
        self.page_size_cap = page_size_cap
        self.requests: list[httpx.Request] = []
        self.forced: list[httpx.Response] = []  # responses returned first, in order

    def _page(self, items: list[dict], request: httpx.Request) -> dict:
        start = int(request.url.params.get("after") or 0)
        limit = min(int(request.url.params.get("limit") or 25), self.page_size_cap)
        chunk = items[start : start + limit]
        body = {"data": chunk}
        nxt = start + limit
        if nxt < len(items):
            body["paging"] = {"cursors": {"before": str(start), "after": str(nxt)}, "next": "https://x/next"}
        return body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.forced:
            return self.forced.pop(0)
        path = request.url.path
        p = request.url.params
        if path.endswith("/keyword_search"):
            return httpx.Response(200, json=self._page(self.search_results.get(p["q"], []), request))
        if path.endswith("/profile_lookup"):
            prof = self.profiles.get(p["username"])
            if prof is None:
                return httpx.Response(404, json={"error": {"message": "not found", "code": 100}})
            return httpx.Response(200, json=prof)
        if path.endswith("/profile_posts"):
            if p["username"] not in self.profile_posts:
                return httpx.Response(403, json={"error": {"message": "no permission", "code": 10}})
            return httpx.Response(200, json=self._page(self.profile_posts[p["username"]], request))
        if path.endswith("/me"):
            return httpx.Response(200, json={"id": "1", "username": "me_account"})
        return httpx.Response(404, json={"error": {"message": "unknown path " + path}})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def err(status: int, code: int | None = None, headers=None) -> httpx.Response:
    body = {"error": {"message": f"err {status}", "type": "OAuthException", "code": code, "fbtrace_id": "abc"}}
    return httpx.Response(status, content=json.dumps(body), headers={"content-type": "application/json", **(headers or {})})
