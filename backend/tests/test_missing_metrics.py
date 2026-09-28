from app.models import Creator
from app.schemas import FOLLOWERS_UNAVAILABLE
from app.serializers import creator_out
from app.services.audience import NullAudienceProvider, OfficialThreadsAudienceProvider
from app.services.scoring import engagement_score
from tests.fake_threads import FakeThreadsAPI, err
from tests.test_threads_client import make_client


async def test_official_provider_returns_count_when_present():
    api = FakeThreadsAPI()
    api.profiles["alice"] = {"username": "alice", "follower_count": 42300}
    prov = OfficialThreadsAudienceProvider(make_client(api))
    assert await prov.get_follower_count("alice") == 42300
    res = await prov.get_audience("alice")
    assert res.source == "threads_profile_lookup" and res.status == "ok"


async def test_official_provider_returns_none_when_field_missing():
    api = FakeThreadsAPI()
    api.profiles["bob"] = {"username": "bob", "name": "Bob"}
    prov = OfficialThreadsAudienceProvider(make_client(api))
    assert await prov.get_follower_count("bob") is None
    assert (await prov.get_audience("bob")).status == "unavailable"


async def test_official_provider_returns_none_without_permission():
    api = FakeThreadsAPI()
    api.forced = [err(403, 10)]
    res = await OfficialThreadsAudienceProvider(make_client(api)).get_audience("alice")
    assert res.follower_count is None and res.status == "permission_denied"


async def test_official_provider_not_found_and_errors():
    api = FakeThreadsAPI()
    prov = OfficialThreadsAudienceProvider(make_client(api))
    assert (await prov.get_audience("ghost")).status == "not_found"
    api.forced = [err(500), err(500), err(500)]
    assert (await prov.get_audience("x")).status == "error"


async def test_null_provider():
    assert await NullAudienceProvider().get_follower_count("x") is None


def test_serializer_marks_unavailable_metrics():
    c = Creator(id=1, username="x", profile_url="https://www.threads.net/@x", status="new",
                activity_source="keyword_search_sample", posts_30d=2)
    out = creator_out(c)
    assert out.followers.available is False
    assert out.followers.value is None
    assert out.followers.note == FOLLOWERS_UNAVAILABLE
    assert out.profile_likes.available is False
    assert out.posts_30d.available and "Lower bound" in out.posts_30d.note
    assert out.monetization_label is None


def test_engagement_unavailable_when_no_real_counts():
    assert engagement_score(post_likes=[None, None], post_replies=[None, None], profile_interactions={"likes": None}) == (None, None)
    score, src = engagement_score(profile_interactions={"likes": 1000, "replies": None})
    assert src == "profile_lookup" and 0 < score < 100
    score2, src2 = engagement_score(post_likes=[10, None], post_replies=[2, None])
    assert src2 == "per_post" and score2 > 0
