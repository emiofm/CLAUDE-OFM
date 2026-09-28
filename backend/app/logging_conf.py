"""Tagged, secret-redacting logging.

Log lines look like ``[THREADS] keyword=brunette results_received=50``.
Any access token / client secret that slips into a message is redacted.
"""
import logging
import re

_SECRET_PATTERNS = [
    re.compile(r"(access_token=)[^&\s\"']+", re.I),
    re.compile(r"(client_secret=)[^&\s\"']+", re.I),
    re.compile(r"(input_token=)[^&\s\"']+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-|]+", re.I),
    re.compile(r"(\"access_token\"\s*:\s*\")[^\"]+", re.I),
    re.compile(r"(TH\|)[^\s&\"']+"),
]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r"\1***REDACTED***", text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger("creator_finder")
    root.handlers = [handler]
    root.setLevel(level.upper())
    root.propagate = False


def get_logger(tag: str) -> "TaggedLogger":
    return TaggedLogger(tag)


class TaggedLogger:
    """Tiny wrapper producing ``[TAG] key=value`` style lines."""

    def __init__(self, tag: str):
        self.tag = tag.upper()
        self._log = logging.getLogger(f"creator_finder.{tag.lower()}")

    def _fmt(self, msg: str, kv: dict) -> str:
        parts = [f"[{self.tag}]", msg] + [f"{k}={v}" for k, v in kv.items()]
        return " ".join(p for p in parts if p)

    def info(self, msg: str = "", **kv):
        self._log.info(self._fmt(msg, kv))

    def debug(self, msg: str = "", **kv):
        self._log.debug(self._fmt(msg, kv))

    def warning(self, msg: str = "", **kv):
        self._log.warning(self._fmt(msg, kv))

    def error(self, msg: str = "", **kv):
        self._log.error(self._fmt(msg, kv))
