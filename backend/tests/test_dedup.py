from app.services.dedup import dedupe_creators, normalize_username, rank_candidates
from tests.fake_threads import post


def test_one_creator_per_username_across_keywords_and_case():
    results = {
        "brunette": [post(1, "Alice"), post(2, "alice"), post(3, "bob")],
        "creator": [post(1, "alice"), post(4, "@ALICE"), post(5, "carol")],
    }
    creators = dedupe_creators(results)
    assert set(creators) == {"alice", "bob", "carol"}
    alice = creators["alice"]
    assert set(alice.posts) == {"1", "2", "4"}  # post 1 counted once
    assert alice.keywords == {"brunette", "creator"}
    assert alice.post_keywords["1"] == {"brunette", "creator"}


def test_posts_without_username_or_id_are_skipped():
    creators = dedupe_creators({"k": [{"id": "1"}, {"username": "x"}, post(2, "y")]})
    assert set(creators) == {"y"}


def test_rank_candidates_prefers_multi_keyword_creators():
    creators = dedupe_creators(
        {"a": [post(1, "one"), post(2, "two"), post(3, "two")], "b": [post(4, "one")]}
    )
    ranked = rank_candidates(creators, 10)
    assert ranked[0].username == "one"
    assert len(rank_candidates(creators, 1)) == 1


def test_normalize_username():
    assert normalize_username(" @Foo ") == "foo"
    assert normalize_username("") is None
