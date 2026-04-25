from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_profile_business_and_qr_resolution(client: TestClient) -> None:
    merchant_headers = auth_headers("merchant-1", "Baqala Al Noor")
    customer_headers = auth_headers("customer-1", "Ahmed")

    profile = client.patch(
        "/api/v1/profiles/me",
        headers=merchant_headers,
        json={"name": "Baqala Al Noor", "phone": "+966500000001", "account_type": "business"},
    )
    assert profile.status_code == 200

    business = client.post(
        "/api/v1/profiles/business-profile",
        headers=merchant_headers,
        json={"shop_name": "Baqala Al Noor", "activity_type": "Grocery", "location": "Riyadh", "description": "Neighborhood grocery"},
    )
    assert business.status_code == 201

    client.get("/api/v1/profiles/me", headers=customer_headers)
    qr = client.get("/api/v1/qr/current", headers=customer_headers)
    assert qr.status_code == 200

    resolved = client.get(f"/api/v1/qr/resolve/{qr.json()['token']}", headers=merchant_headers)
    assert resolved.status_code == 200
    assert resolved.json()["id"] == "customer-1"


def test_group_visibility_requires_acceptance(client: TestClient) -> None:
    owner_headers = auth_headers("owner-1")
    friend_headers = auth_headers("friend-1")

    client.get("/api/v1/profiles/me", headers=owner_headers)
    client.get("/api/v1/profiles/me", headers=friend_headers)
    group = client.post("/api/v1/groups", headers=owner_headers, json={"name": "Family"})
    group_id = group.json()["id"]

    invite = client.post(f"/api/v1/groups/{group_id}/invite", headers=owner_headers, json={"user_id": "friend-1"})
    assert invite.status_code == 200
    assert invite.json()["status"] == "pending"

    accepted = client.post(f"/api/v1/groups/{group_id}/accept", headers=friend_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    debt = client.post(
        "/api/v1/debts",
        headers=owner_headers,
        json={
            "debtor_name": "Friend",
            "debtor_id": "friend-1",
            "amount": "10.00",
            "currency": "SAR",
            "description": "Dinner",
            "due_date": str(date.today() + timedelta(days=1)),
            "group_id": group_id,
        },
    )
    assert debt.status_code == 201

    group_debts = client.get(f"/api/v1/groups/{group_id}/debts", headers=friend_headers)
    assert group_debts.status_code == 200
    assert group_debts.json()[0]["id"] == debt.json()["id"]


def test_ai_requires_subscription_and_extracts_draft(client: TestClient) -> None:
    merchant_headers = auth_headers("merchant-1")
    forbidden = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=merchant_headers,
        json={"transcript": "على Ahmed 25 SAR groceries due 2026-05-01"},
    )
    assert forbidden.status_code == 403

    client.patch("/api/v1/profiles/me", headers=merchant_headers, json={"ai_enabled": True})
    draft = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=merchant_headers,
        json={"transcript": "على Ahmed 25 SAR groceries due 2026-05-01", "default_currency": "SAR"},
    )
    assert draft.status_code == 200
    assert draft.json()["amount"] == "25"
    assert draft.json()["currency"] == "SAR"

