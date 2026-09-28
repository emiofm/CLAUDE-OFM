"""Threads username parsing/validation."""
from __future__ import annotations

import re

# Threads/Instagram usernames: letters, digits, "." and "_", up to 30 chars.
USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?threads\.(?:net|com)/@?([A-Za-z0-9._]+)", re.I)


def normalize(raw: str) -> str | None:
    """Accept '@user', 'user', or a threads.net / threads.com profile URL."""
    if not raw:
        return None
    s = raw.strip()
    m = _URL_RE.search(s)
    if m:
        s = m.group(1)
    s = s.lstrip("@").strip().lower().rstrip("/")
    if not USERNAME_RE.match(s) or s.startswith(".") or s.endswith(".") or ".." in s:
        return None
    return s


def parse_many(text_or_list: str | list[str]) -> tuple[list[str], list[str]]:
    """Split on commas/whitespace/newlines. Returns (valid unique, invalid)."""
    items = text_or_list if isinstance(text_or_list, list) else re.split(r"[\s,;]+", text_or_list)
    valid: list[str] = []
    invalid: list[str] = []
    for item in items:
        if not item or not item.strip():
            continue
        u = normalize(item)
        if u is None:
            invalid.append(item.strip())
        elif u not in valid:
            valid.append(u)
    return valid, invalid
