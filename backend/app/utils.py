from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; treat naive datetimes as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_threads_timestamp(value: str | None) -> datetime | None:
    """Threads returns ISO 8601 like ``2024-07-01T12:34:56+0000``."""
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    if len(v) > 5 and v[-5] in "+-" and v[-3] != ":":
        v = v[:-2] + ":" + v[-2:]
    try:
        return to_aware(datetime.fromisoformat(v))
    except ValueError:
        return None
