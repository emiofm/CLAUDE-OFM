import pytest

from app.services.app_config import ScoreWeights
from app.services.scoring import (
    FilterInput,
    apply_filters,
    audience_score,
    detect_signals,
    keyword_relevance,
    total_score,
)


def test_default_weights():
    w = ScoreWeights()
    assert (w.visual_similarity, w.activity, w.engagement, w.creator_signal, w.keyword_relevance) == (
        45, 25, 15, 10, 5)
    assert w.audience == 0


def test_total_with_all_components():
    comps = dict(visual_similarity=100, activity=100, engagement=100, creator_signal=100, keyword_relevance=100)
    total, bd = total_score(comps, ScoreWeights())
    assert total == 100
    assert bd["unavailable"] == []


def test_ranking_order():
    w = ScoreWeights()
    a, _ = total_score(dict(visual_similarity=90, activity=50, engagement=None, creator_signal=20, keyword_relevance=50), w)
    b, _ = total_score(dict(visual_similarity=40, activity=90, engagement=None, creator_signal=90, keyword_relevance=100), w)
    assert a > b  # visual similarity dominates by default


def test_missing_components_are_excluded_not_zeroed():
    comps = dict(visual_similarity=80, activity=60, engagement=None, creator_signal=None, keyword_relevance=None)
    total, bd = total_score(comps, ScoreWeights())
    assert total == pytest.approx((45 * 80 + 25 * 60) / 70, abs=0.01)
    assert set(bd["unavailable"]) == {"engagement", "creator_signal", "keyword_relevance"}
    assert sum(bd["effective_weights"].values()) == pytest.approx(100, abs=0.01)


def test_audience_only_counts_when_weighted_and_available():
    comps = dict(visual_similarity=50, audience=None)
    total, bd = total_score(comps, ScoreWeights(audience=10))
    assert total == 50 and "audience" in bd["unavailable"]
    total2, _ = total_score(dict(visual_similarity=50, audience=100), ScoreWeights(audience=0))
    assert total2 == 50  # weight 0 -> ignored entirely
    assert audience_score(None) is None
    assert audience_score(1_000_000) == 100


def test_weights_validation():
    with pytest.raises(ValueError):
        ScoreWeights(visual_similarity=0, activity=0, engagement=0, creator_signal=0, keyword_relevance=0)


def test_creator_signals_are_only_possible():
    r = detect_signals(["Lifestyle content creator ✨ exclusive content, link in bio", "new post"])
    assert r.monetization == "possible"
    assert r.creator_level in {"medium", "high"}
    assert {"content creator", "exclusive", "link in bio"} <= set(r.terms)
    none = detect_signals(["I love coffee and hiking", None])
    assert none.creator_level == "none" and none.monetization == "none" and none.creator_score == 0


def test_of_is_case_sensitive():
    assert "OF" in detect_signals(["my OF is up"]).terms
    assert "OF" not in detect_signals(["one of the best"]).terms


def test_keyword_relevance():
    score, matched = keyword_relevance(["brunette", "soft girl", "gym"], ["Soft girl era", "brunette vibes"])
    assert matched == ["brunette", "soft girl"]
    assert score == pytest.approx(66.67)
    s2, m2 = keyword_relevance(["gym"], ["nothing"], search_hits={"gym"})
    assert m2 == ["gym"] and s2 == 100
    assert keyword_relevance([], ["x"]) == (None, [])


def _fi(**kw):
    base = dict(posts_7d=2, posts_30d=10, posts_90d=20, activity_is_lower_bound=False,
                follower_count=None, replies=None, likes=None)
    base.update(kw)
    return FilterInput(**base)


def test_filters_known_values():
    assert apply_filters(_fi(), {"min_posts_30d": 10})[0]
    assert not apply_filters(_fi(), {"min_posts_30d": 11})[0]
    assert not apply_filters(_fi(follower_count=500), {"min_followers": 1000})[0]
    assert not apply_filters(_fi(follower_count=5000), {"max_followers": 1000})[0]


def test_filters_unknown_followers_flagged_not_faked():
    ok, flags = apply_filters(_fi(), {"min_followers": 20000})
    assert ok and "followers_unavailable" in flags
    ok2, _ = apply_filters(_fi(), {"min_followers": 20000, "strict_unknown_metrics": True})
    assert not ok2


def test_lower_bound_activity_is_unverified_not_rejected():
    ok, flags = apply_filters(_fi(posts_30d=3, activity_is_lower_bound=True), {"min_posts_30d": 10})
    assert ok and "posts_30d_unverified" in flags
