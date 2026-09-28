"""Typed Threads API errors with user-facing messages.

Messages never include tokens or secrets.
"""
from __future__ import annotations


class ThreadsAPIError(Exception):
    status_code: int | None = None
    default_user_message = "The Threads API returned an unexpected error."

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
        fbtrace_id: str | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message or self.default_user_message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id
        self.retry_after = retry_after

    @property
    def user_message(self) -> str:
        return self.default_user_message

    def to_dict(self) -> dict:
        return {
            "error": type(self).__name__,
            "status_code": self.status_code,
            "meta_error_code": self.code,
            "meta_error_subcode": self.subcode,
            "message": self.user_message,
            "detail": self.message or None,
            "fbtrace_id": self.fbtrace_id,
            "retry_after_seconds": self.retry_after,
        }


class ThreadsNotConnectedError(ThreadsAPIError):
    status_code = 401
    default_user_message = (
        "Threads is not connected. Open Settings and click 'Connect Threads' to authorize the app."
    )


class ThreadsAuthError(ThreadsAPIError):
    status_code = 401
    default_user_message = (
        "Threads rejected the access token (401). It may be expired or revoked. "
        "Reconnect Threads from Settings."
    )


class ThreadsPermissionError(ThreadsAPIError):
    status_code = 403
    default_user_message = (
        "Threads denied access (403). The app is missing a required permission "
        "(e.g. threads_keyword_search or threads_profile_discovery) or it has not "
        "been approved in App Review yet. Check granted scopes in Settings."
    )


class ThreadsRateLimitError(ThreadsAPIError):
    status_code = 429
    default_user_message = (
        "Threads rate limit reached (429). Requests are paused; try again later. "
        "Keyword search is limited by Meta to a fixed number of queries per rolling 24 hours."
    )


class ThreadsServerError(ThreadsAPIError):
    status_code = 500
    default_user_message = "Threads API is having problems (5xx). Try again in a few minutes."


class ThreadsNotFoundError(ThreadsAPIError):
    status_code = 404
    default_user_message = "The requested Threads resource was not found or is not public."


class ThreadsBadRequestError(ThreadsAPIError):
    status_code = 400
    default_user_message = "Threads rejected the request parameters (400)."


class LocalBudgetExceededError(ThreadsRateLimitError):
    default_user_message = (
        "The local keyword-search budget for the last 24 hours is used up. "
        "This protects the Meta rate limit; raise THREADS_KEYWORD_SEARCH_DAILY_BUDGET carefully."
    )


# Meta Graph error codes that indicate throttling regardless of HTTP status.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80001, 80002}
AUTH_CODES = {102, 190}
PERMISSION_CODES = {10, 200, 299}


def error_from_response(status: int, body: dict | None, retry_after: float | None) -> ThreadsAPIError:
    err = (body or {}).get("error") if isinstance(body, dict) else None
    err = err if isinstance(err, dict) else {}
    kwargs = dict(
        status_code=status,
        code=err.get("code"),
        subcode=err.get("error_subcode"),
        fbtrace_id=err.get("fbtrace_id"),
        retry_after=retry_after,
    )
    message = str(err.get("message") or "")
    code = err.get("code")

    if code in AUTH_CODES or status == 401:
        return ThreadsAuthError(message, **kwargs)
    if status == 429 or code in RATE_LIMIT_CODES:
        kwargs["status_code"] = 429 if status == 429 else status
        return ThreadsRateLimitError(message, **kwargs)
    if status == 403 or code in PERMISSION_CODES:
        return ThreadsPermissionError(message, **kwargs)
    if status == 404:
        return ThreadsNotFoundError(message, **kwargs)
    if status >= 500:
        return ThreadsServerError(message, **kwargs)
    if status == 400:
        return ThreadsBadRequestError(message, **kwargs)
    return ThreadsAPIError(message, **kwargs)
