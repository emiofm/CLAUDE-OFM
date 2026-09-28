import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.usernames import normalize, parse_many


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("@Alice", "alice"),
        (" bob_1 ", "bob_1"),
        ("https://www.threads.net/@carol.x", "carol.x"),
        ("threads.com/@Dana/", "dana"),
        ("https://www.threads.net/@eve/post/123", "eve"),
        ("bad name", None),
        ("..dots", None),
        ("x" * 31, None),
        ("", None),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_parse_many_dedupes_and_reports_invalid():
    valid, invalid = parse_many("@a, b\nhttps://threads.net/@c  @A; bad!name")
    assert valid == ["a", "b", "c"]
    assert invalid == ["bad!name"]


def test_models_accounts_profiles_flow(client):
    m = client.post("/api/models", json={"name": "Sofia", "color": "#8b5cf6"}).json()
    assert m["accounts"] == []

    a1 = client.post(f"/api/models/{m['id']}/accounts", json={"username": "@Sofia.Main", "label": "Main"})
    assert a1.status_code == 201
    acc = a1.json()
    assert acc["username"] == "sofia.main" and acc["position"] == 0
    a2 = client.post(f"/api/models/{m['id']}/accounts", json={"username": "sofia_backup"}).json()
    assert a2["position"] == 1
    dup = client.post(f"/api/models/{m['id']}/accounts", json={"username": "sofia.main"})
    assert dup.status_code == 409
    assert client.post(f"/api/models/{m['id']}/accounts", json={"username": "no spaces"}).status_code == 400

    r = client.post(f"/api/accounts/{acc['id']}/profiles",
                    json={"usernames": "@one, two\nhttps://www.threads.net/@three bad!x @one"}).json()
    assert r["added"] == ["one", "two", "three"]
    assert r["invalid"] == ["bad!x"]
    assert r["account"]["profiles_total"] == 3 and r["account"]["profiles_selected"] == 0
    again = client.post(f"/api/accounts/{acc['id']}/profiles", json={"usernames": ["two", "four"]}).json()
    assert again["added"] == ["four"] and again["duplicates"] == ["two"]

    profiles = client.get(f"/api/accounts/{acc['id']}").json()["profiles"]
    pid = profiles[0]["id"]
    assert client.patch(f"/api/profiles/{pid}", json={"selected": True}).json()["selected"] is True
    sel = client.post(f"/api/accounts/{acc['id']}/profiles/select",
                      json={"selected": True, "ids": [profiles[1]["id"], profiles[2]["id"]]}).json()
    assert sel["profiles_selected"] == 3
    none = client.post(f"/api/accounts/{acc['id']}/profiles/select", json={"selected": False}).json()
    assert none["profiles_selected"] == 0

    assert client.delete(f"/api/profiles/{pid}").json() == {"deleted": True}
    assert client.get(f"/api/accounts/{acc['id']}").json()["profiles_total"] == 3

    # Same username can be a target of different accounts independently.
    r2 = client.post(f"/api/accounts/{a2['id']}/profiles", json={"usernames": "two"}).json()
    assert r2["added"] == ["two"]

    flat = client.get("/api/accounts").json()
    assert {x["username"] for x in flat} == {"sofia.main", "sofia_backup"}
    assert flat[0]["talent_name"] == "Sofia"

    listing = client.get("/api/models").json()
    assert listing[0]["accounts"][0]["profiles_total"] == 3

    renamed = client.patch(f"/api/accounts/{acc['id']}", json={"username": "sofia.new", "label": "Primary"}).json()
    assert renamed["username"] == "sofia.new" and renamed["label"] == "Primary"
    assert client.patch(f"/api/models/{m['id']}", json={"name": "Sofia R"}).json()["name"] == "Sofia R"

    # Deleting a model removes its accounts and their lists.
    assert client.delete(f"/api/models/{m['id']}").json() == {"deleted": True}
    assert client.get("/api/accounts").json() == []
    assert client.get(f"/api/accounts/{acc['id']}").status_code == 404


def test_profile_list_is_enriched_with_search_engine_data(client):
    from app.db import SessionLocal
    from app.models import Creator

    db = SessionLocal()
    db.add(Creator(username="known", profile_url="https://www.threads.net/@known", status="new",
                   display_name="Known Creator", follower_count=1200, follower_source="threads_profile_lookup"))
    db.commit()
    db.close()
    m = client.post("/api/models", json={"name": "M"}).json()
    acc = client.post(f"/api/models/{m['id']}/accounts", json={"username": "acct"}).json()
    r = client.post(f"/api/accounts/{acc['id']}/profiles",
                    json={"usernames": ["known", "unknown"], "source": "search"}).json()
    profiles = {p["username"]: p for p in r["account"]["profiles"]}
    assert profiles["known"]["creator"]["display_name"] == "Known Creator"
    assert profiles["known"]["creator"]["followers"]["value"] == 1200
    assert profiles["known"]["source"] == "search"
    assert profiles["unknown"]["creator"] is None


def test_validation_errors(client):
    assert client.post("/api/models", json={"name": ""}).status_code == 422
    assert client.post("/api/models", json={"name": "x", "color": "red"}).status_code == 422
    assert client.post("/api/models/999/accounts", json={"username": "a"}).status_code == 404
    m = client.post("/api/models", json={"name": "M"}).json()
    acc = client.post(f"/api/models/{m['id']}/accounts", json={"username": "acct"}).json()
    assert client.post(f"/api/accounts/{acc['id']}/profiles", json={"usernames": "  "}).status_code == 400
