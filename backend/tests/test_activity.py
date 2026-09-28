from datetime import datetime, timedelta, timezone

from app.services.app_config import ActivityConfig
from app.services.scoring import activity_score, count_activity

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def stamps(*days):
    return [NOW - timedelta(days=d) for d in days]


def test_counts_windows_and_recency():
    c = count_activity(stamps(0.5, 3, 10, 29, 60, 89, 120) + [None], now=NOW)
    assert (c.posts_7d, c.posts_30d, c.posts_90d) == (2, 4, 6)
    assert round(c.days_since_last_post, 2) == 0.5


def test_duplicate_timestamps_counted_once():
    c = count_activity(stamps(1, 1, 1), now=NOW)
    assert c.posts_7d == 1


def test_no_posts_means_unavailable_not_zero():
    assert activity_score(count_activity([], now=NOW), ActivityConfig()) is None


def test_more_recent_activity_scores_higher():
    cfg = ActivityConfig()
    active = activity_score(count_activity(stamps(*range(0, 30, 2)), now=NOW), cfg)
    stale = activity_score(count_activity(stamps(60, 70, 80), now=NOW), cfg)
    assert active > stale > 0


def test_saturates_at_targets():
    cfg = ActivityConfig()
    target = activity_score(count_activity(stamps(*[i * 1.5 for i in range(60)]), now=NOW), cfg)
    assert target == 100.0 or target > 95


def test_spam_is_not_rewarded():
    cfg = ActivityConfig()
    healthy = activity_score(count_activity(stamps(*[i * 1.4 for i in range(64)]), now=NOW), cfg)
    spam = activity_score(count_activity(stamps(*[i / 50 for i in range(1500)]), now=NOW), cfg)
    assert spam < healthy


def test_weights_are_configurable():
    counts = count_activity(stamps(40), now=NOW)
    only_recency = ActivityConfig(weight_7d=0, weight_30d=0, weight_90d=0, weight_recency=1)
    only_90d = ActivityConfig(weight_7d=0, weight_30d=0, weight_90d=1, weight_recency=0, target_90d=1)
    assert activity_score(counts, only_90d) == 100.0
    assert activity_score(counts, only_recency) < 20
