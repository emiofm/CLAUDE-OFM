"""Activity, signals, engagement and ranking.

Every component returns a 0-100 score or ``None`` when its inputs are not
available. ``None`` components are excluded from the weighted total (weights
are re-normalised over the available ones) instead of being treated as zero,
so missing data never masquerades as a real measurement.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..utils import to_aware
from .app_config import ActivityConfig, ScoreWeights


# ------------------------------------------------------------------ activity
@dataclass
class ActivityCounts:
    posts_7d: int
    posts_30d: int
    posts_90d: int
    last_post_at: datetime | None
    days_since_last_post: float | None


def count_activity(timestamps: list[datetime | None], now: datetime | None = None) -> ActivityCounts:
    now = now or datetime.now(timezone.utc)
    ts = sorted({to_aware(t) for t in timestamps if t is not None}, reverse=True)
    ts = [t for t in ts if t <= now + timedelta(minutes=5)]

    def within(days: int) -> int:
        return sum(1 for t in ts if now - t <= timedelta(days=days))

    last = ts[0] if ts else None
    days_since = max(0.0, (now - last).total_seconds() / 86400) if last else None
    return ActivityCounts(within(7), within(30), within(90), last, days_since)


def _saturate(n: int, target: int) -> float:
    return min(n, target) / target


def activity_score(counts: ActivityCounts, cfg: ActivityConfig) -> float | None:
    """Weighted mix of 7d/30d/90d volume and recency, with spam damping.

    Volumes saturate at their targets so posting more never keeps adding
    score; above ``spam_posts_per_day`` the whole score is damped.
    """
    if counts.last_post_at is None:
        return None
    parts = {
        "7d": (cfg.weight_7d, _saturate(counts.posts_7d, cfg.target_7d)),
        "30d": (cfg.weight_30d, _saturate(counts.posts_30d, cfg.target_30d)),
        "90d": (cfg.weight_90d, _saturate(counts.posts_90d, cfg.target_90d)),
        "recency": (
            cfg.weight_recency,
            0.5 ** ((counts.days_since_last_post or 0.0) / cfg.recency_half_life_days),
        ),
    }
    total_w = sum(w for w, _ in parts.values()) or 1.0
    score = sum(w * v for w, v in parts.values()) / total_w

    per_day = max(counts.posts_7d / 7, counts.posts_30d / 30)
    if per_day > cfg.spam_posts_per_day:
        score *= max(0.3, cfg.spam_posts_per_day / per_day)
    return round(score * 100, 2)


# ------------------------------------------------------------------- signals
@dataclass(frozen=True)
class SignalPattern:
    label: str
    regex: re.Pattern
    weight: float
    monetization: bool = False


def _p(label, pattern, weight, monetization=False, flags=re.I):
    return SignalPattern(label, re.compile(pattern, flags), weight, monetization)


SIGNAL_PATTERNS: list[SignalPattern] = [
    _p("onlyfans", r"\bonly\s?fans\b|onlyfans\.com", 3, True),
    _p("OF", r"(?<![A-Za-z])OF(?![A-Za-z])", 1.5, True, flags=0),
    _p("fansly", r"\bfansly\b", 3, True),
    _p("exclusive", r"\bexclusive(s)?\b", 1, True),
    _p("subscribe", r"\bsubscri(be|ption|bers?)\b", 1, True),
    _p("vip", r"\bvip\b", 1, True),
    _p("spicy", r"\bspicy\b|🌶|🔞", 1, True),
    _p("fans", r"\bfans\b", 0.5, True),
    _p("link in bio", r"\blink\s+in\s+(my\s+)?bio\b|\blink\s+below\b", 1.5, True),
    _p("linktree", r"\blinktr\.ee\b|\blinktree\b", 1.5, True),
    _p("beacons", r"\bbeacons\.(ai|page)\b|\bbeacons\b", 1.5, True),
    _p("allmylinks", r"\ballmylinks\b", 1.5, True),
    _p("content creator", r"\bcontent\s+creator\b", 2),
    _p("creator", r"\bcreator\b", 1),
    _p("influencer", r"\binfluencer\b", 1),
    _p("model", r"\bmodel(ing)?\b", 1),
    _p("collab", r"\bcollabs?\b|\bcollaborations?\b", 0.5),
    _p("brand deals", r"\bbrand\s+deals?\b|\bpr\s+friendly\b|\bbusiness\s+inquir(y|ies)\b", 1),
]


@dataclass
class SignalResult:
    creator_score: float  # 0-100
    creator_level: str  # none / low / medium / high
    monetization: str  # none / possible
    terms: list[str] = field(default_factory=list)


def detect_signals(texts: list[str | None]) -> SignalResult:
    """Detect creator / *possible* monetization signals in bio + post text.

    A match is only a hint ("Possible monetization signal"); it never
    asserts that a person has an account on any platform.
    """
    blob = "\n".join(t for t in texts if t)
    terms: list[str] = []
    raw = 0.0
    monetization_hits = 0
    for pat in SIGNAL_PATTERNS:
        if pat.regex.search(blob):
            terms.append(pat.label)
            raw += pat.weight
            monetization_hits += int(pat.monetization)
    score = round(min(raw, 6.0) / 6.0 * 100, 2)
    level = "none" if raw == 0 else "low" if raw < 2 else "medium" if raw < 4 else "high"
    return SignalResult(score, level, "possible" if monetization_hits else "none", terms)


# ---------------------------------------------------------- keyword relevance
def keyword_relevance(
    keywords: list[str], texts: list[str | None], search_hits: set[str] | None = None
) -> tuple[float | None, list[str]]:
    kws = [k.strip() for k in keywords if k and k.strip()]
    if not kws:
        return None, []
    blob = " ".join(t for t in texts if t).lower()
    hits = {k.lower() for k in (search_hits or set())}
    matched = []
    for kw in kws:
        k = kw.lower()
        if k in hits or re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", blob):
            matched.append(kw)
    return round(len(matched) / len(kws) * 100, 2), matched


# ------------------------------------------------------ engagement / audience
def _log_scale(value: float, lo: float, hi: float) -> float:
    if value <= lo:
        return 0.0
    return min(1.0, math.log10(value / lo) / math.log10(hi / lo))


def engagement_score(
    *,
    post_likes: list[int | None] | None = None,
    post_replies: list[int | None] | None = None,
    profile_interactions: dict[str, int | None] | None = None,
) -> tuple[float | None, str | None]:
    """Engagement from whatever *real* counts exist.

    1. Per-post likes/replies (only if a source provides them).
    2. Profile-level likes/replies/reposts/quotes from profile_lookup.
    Otherwise None (unavailable) — never estimated.
    """
    per_post = [
        (l or 0) + (r or 0)
        for l, r in zip(post_likes or [], post_replies or [])
        if l is not None or r is not None
    ]
    if per_post:
        avg = sum(per_post) / len(per_post)
        return round(_log_scale(avg + 1, 1, 5000) * 100, 2), "per_post"
    if profile_interactions:
        vals = [v for v in profile_interactions.values() if isinstance(v, int)]
        if vals:
            return round(_log_scale(sum(vals) + 1, 10, 1_000_000) * 100, 2), "profile_lookup"
    return None, None


def audience_score(follower_count: int | None) -> float | None:
    if follower_count is None:
        return None
    return round(_log_scale(follower_count, 1_000, 1_000_000) * 100, 2)


# ------------------------------------------------------------------- ranking
def total_score(components: dict[str, float | None], weights: ScoreWeights) -> tuple[float, dict]:
    """Weighted average over *available* components.

    Returns (total 0-100, breakdown) where breakdown lists effective weights,
    contributions and which components were unavailable.
    """
    w = weights.model_dump()
    used: dict[str, float] = {}
    unavailable: list[str] = []
    for name, value in components.items():
        weight = w.get(name, 0.0)
        if weight <= 0:
            continue
        if value is None:
            unavailable.append(name)
            continue
        used[name] = weight
    total_w = sum(used.values())
    if total_w == 0:
        return 0.0, {"effective_weights": {}, "contributions": {}, "unavailable": unavailable}
    eff = {k: v / total_w for k, v in used.items()}
    contrib = {k: round(eff[k] * float(components[k]), 2) for k in used}
    return round(sum(contrib.values()), 2), {
        "effective_weights": {k: round(v * 100, 2) for k, v in eff.items()},
        "contributions": contrib,
        "unavailable": unavailable,
    }


# ------------------------------------------------------------------- filters
@dataclass
class FilterInput:
    posts_7d: int | None
    posts_30d: int | None
    posts_90d: int | None
    activity_is_lower_bound: bool
    follower_count: int | None
    replies: int | None
    likes: int | None


def apply_filters(m: FilterInput, filters: dict) -> tuple[bool, list[str]]:
    """Return (passes, flags).

    Known values below a minimum exclude the creator. Unknown values pass with
    a flag unless ``strict_unknown_metrics`` is set. Activity counts from the
    keyword-search sample are lower bounds: meeting the minimum is conclusive,
    missing it is flagged as unverified.
    """
    strict = bool(filters.get("strict_unknown_metrics"))
    flags: list[str] = []

    def check_min(key: str, value: int | None, lower_bound: bool = False, label: str = "") -> bool:
        minimum = filters.get(key)
        if minimum in (None, "", 0):
            return True
        if value is None:
            flags.append(f"{label}_unavailable")
            return not strict
        if value >= minimum:
            return True
        if lower_bound:
            flags.append(f"{label}_unverified")
            return not strict
        return False

    ok = all(
        [
            check_min("min_posts_7d", m.posts_7d, m.activity_is_lower_bound, "posts_7d"),
            check_min("min_posts_30d", m.posts_30d, m.activity_is_lower_bound, "posts_30d"),
            check_min("min_posts_90d", m.posts_90d, m.activity_is_lower_bound, "posts_90d"),
            check_min("min_followers", m.follower_count, False, "followers"),
            check_min("min_replies", m.replies, False, "replies"),
            check_min("min_likes", m.likes, False, "likes"),
        ]
    )
    max_f = filters.get("max_followers")
    if max_f not in (None, "", 0):
        if m.follower_count is None:
            if "followers_unavailable" not in flags:
                flags.append("followers_unavailable")
            ok = ok and not strict
        elif m.follower_count > max_f:
            ok = False
    return ok, flags
