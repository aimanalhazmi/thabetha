from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_two_party_debt_and_payment_lifecycle(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-1", "Baqala Al Noor")
    debtor_headers = auth_headers("customer-1", "Ahmed")

    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)

    create_response = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Ahmed",
            "debtor_id": "customer-1",
            "amount": "25.00",
            "currency": "SAR",
            "description": "Groceries",
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert create_response.status_code == 201
    debt = create_response.json()
    assert debt["status"] == "pending_confirmation"

    accepted = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=debtor_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    payment = client.post(f"/api/v1/debts/{debt['id']}/mark-paid", headers=debtor_headers, json={"note": "Paid in cash"})
    assert payment.status_code == 200
    assert payment.json()["status"] == "pending_creditor_confirmation"

    confirmed = client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=creditor_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"

    debtor_dashboard = client.get("/api/v1/dashboard/debtor", headers=debtor_headers)
    assert debtor_dashboard.status_code == 200
    assert debtor_dashboard.json()["commitment_score"] == 55


def test_unrelated_user_cannot_read_debt(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-1")
    debtor_headers = auth_headers("customer-1")
    outsider_headers = auth_headers("outsider-1")

    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)
    response = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Ahmed",
            "debtor_id": "customer-1",
            "amount": "25.00",
            "currency": "SAR",
            "description": "Groceries",
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )

    debt_id = response.json()["id"]
    forbidden = client.get(f"/api/v1/debts/{debt_id}", headers=outsider_headers)
    assert forbidden.status_code == 403

