"""Tests for profiles.preferred_language round-trip.

Covers the five surfaces from contracts/profile-locale.md:
  1. Default 'ar' on first fetch.
  2. PATCH sets the value; follow-up GET returns the new value.
  3. PATCH with an invalid value returns 422.
  4. One user's PATCH does not affect another user's profile.
  5. (Migration round-trip is a Postgres concern; covered here by verifying the
     in-memory default mirrors the DB default, i.e. 'ar'.)
"""
from tests.conftest import auth_headers


def test_preferred_language_default_is_ar(client):
    headers = auth_headers("user-001")
    resp = client.get("/api/v1/profiles/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "ar"


def test_patch_preferred_language_en_then_get(client):
    headers = auth_headers("user-002")
    # Ensure profile exists
    client.get("/api/v1/profiles/me", headers=headers)

    resp = client.patch(
        "/api/v1/profiles/me",
        json={"preferred_language": "en"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "en"

    # Follow-up GET returns updated value
    resp = client.get("/api/v1/profiles/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "en"


def test_patch_preferred_language_back_to_ar(client):
    headers = auth_headers("user-003")
    client.get("/api/v1/profiles/me", headers=headers)
    client.patch("/api/v1/profiles/me", json={"preferred_language": "en"}, headers=headers)

    resp = client.patch(
        "/api/v1/profiles/me",
        json={"preferred_language": "ar"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "ar"


def test_patch_invalid_preferred_language_returns_422(client):
    headers = auth_headers("user-004")
    client.get("/api/v1/profiles/me", headers=headers)

    resp = client.patch(
        "/api/v1/profiles/me",
        json={"preferred_language": "fr"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_patch_does_not_affect_other_user(client):
    headers_a = auth_headers("user-005a")
    headers_b = auth_headers("user-005b")

    client.get("/api/v1/profiles/me", headers=headers_a)
    client.get("/api/v1/profiles/me", headers=headers_b)

    client.patch("/api/v1/profiles/me", json={"preferred_language": "en"}, headers=headers_a)

    resp_b = client.get("/api/v1/profiles/me", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["preferred_language"] == "ar"
