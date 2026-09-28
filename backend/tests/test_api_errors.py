import httpx
import pytest

from app.logging_conf import redact
from app.threads.errors import (
    ThreadsAuthError,
    ThreadsPermissionError,
    ThreadsRateLimitError,
    ThreadsServerError,
    error_from_response,
)
from tests.fake_threads import FakeThreadsAPI, err
from tests.test_threads_client import make_client


@pytest.mark.parametrize(
    "status,code,exc",
    [
        (401, 190, ThreadsAuthError),
        (403, 10, ThreadsPermissionError),
        (429, None, ThreadsRateLimitError),
        (400, 190, ThreadsAuthError),
        (400, 4, ThreadsRateLimitError),
        (400, 613, ThreadsRateLimitError),
        (500, 1, ThreadsServerError),
        (503, None, ThreadsServerError),
    ],
)
def test_error_mapping(status, code, exc):
    e = error_from_response(status, {"error": {"message": "m", "code": code}}, None)
    assert isinstance(e, exc)
    assert e.user_message


async def test_401_raises_auth_error_without_retry():
    api = FakeThreadsAPI()
    api.forced = [err(401, 190)]
    with pytest.raises(ThreadsAuthError) as ei:
        await make_client(api).keyword_search("x")
    assert len(api.requests) == 1
    assert "Reconnect" in ei.value.user_message


async def test_403_permission_error():
    api = FakeThreadsAPI()
    api.forced = [err(403, 10)]
    with pytest.raises(ThreadsPermissionError) as ei:
        await make_client(api).keyword_search("x")
    assert "threads_keyword_search" in ei.value.user_message


async def test_429_with_short_retry_after_is_honoured_once():
    api = FakeThreadsAPI()
    api.forced = [err(429, headers={"Retry-After": "2"})]
    slept = []

    async def sleep(s):
        slept.append(s)

    from app.threads.client import ThreadsClient

    client = ThreadsClient(lambda: "t", graph_url="https://g/v1.0", transport=api.transport(), sleep=sleep)
    assert await client.keyword_search("x") == []
    assert slept == [2.0]


async def test_429_without_retry_after_is_not_retried():
    api = FakeThreadsAPI()
    api.forced = [err(429), err(429)]
    with pytest.raises(ThreadsRateLimitError):
        await make_client(api).keyword_search("x")
    assert len(api.requests) == 1


async def test_429_long_retry_after_surfaces_error():
    api = FakeThreadsAPI()
    api.forced = [err(429, headers={"Retry-After": "3600"})]
    with pytest.raises(ThreadsRateLimitError) as ei:
        await make_client(api).keyword_search("x")
    assert ei.value.retry_after == 3600


async def test_500_retries_then_fails():
    api = FakeThreadsAPI()
    api.forced = [err(500), err(500), err(500)]
    with pytest.raises(ThreadsServerError):
        await make_client(api, max_retries=2).keyword_search("x")
    assert len(api.requests) == 3


async def test_500_then_success():
    api = FakeThreadsAPI()
    api.forced = [err(500)]
    assert await make_client(api).keyword_search("x") == []
    assert len(api.requests) == 2


async def test_non_json_error_body():
    api = FakeThreadsAPI()
    api.forced = [httpx.Response(502, text="<html>bad gateway</html>")] * 3
    with pytest.raises(ThreadsServerError):
        await make_client(api).keyword_search("x")


def test_error_dict_never_contains_token():
    e = error_from_response(401, {"error": {"message": "Invalid OAuth access token", "code": 190}}, None)
    d = e.to_dict()
    assert d["status_code"] == 401 and d["meta_error_code"] == 190
    assert "super-secret-value" not in str(d)


def test_redaction():
    line = "GET https://g/x?access_token=ABC123&client_secret=S3CR3T Bearer XYZ.789 TH|1|secret"
    out = redact(line)
    for secret in ("ABC123", "S3CR3T", "XYZ.789", "1|secret"):
        assert secret not in out
