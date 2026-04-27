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
    # Paid before due_date → +3 (early-payment indicator).
    assert debtor_dashboard.json()["commitment_score"] == 53


def test_creditor_approves_edit_request_updates_terms(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-2", "Shop")
    debtor_headers = auth_headers("customer-2", "Sara")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)

    create = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Sara",
            "debtor_id": "customer-2",
            "amount": "100.00",
            "currency": "SAR",
            "description": "Order",
            "due_date": str(date.today() + timedelta(days=5)),
        },
    )
    debt_id = create.json()["id"]

    requested = client.post(
        f"/api/v1/debts/{debt_id}/edit-request",
        headers=debtor_headers,
        json={"message": "Amount is wrong", "requested_amount": "80.00"},
    )
    assert requested.status_code == 200
    assert requested.json()["status"] == "edit_requested"

    approved = client.post(
        f"/api/v1/debts/{debt_id}/edit-request/approve",
        headers=creditor_headers,
        json={"message": "Agreed"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "pending_confirmation"
    assert approved.json()["amount"] == "80.00"


def test_creditor_rejects_edit_request_keeps_original_terms(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-3", "Shop")
    debtor_headers = auth_headers("customer-3", "Khalid")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)

    create = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Khalid",
            "debtor_id": "customer-3",
            "amount": "50.00",
            "currency": "SAR",
            "description": "Order",
            "due_date": str(date.today() + timedelta(days=3)),
        },
    )
    debt_id = create.json()["id"]

    client.post(
        f"/api/v1/debts/{debt_id}/edit-request",
        headers=debtor_headers,
        json={"message": "Lower it", "requested_amount": "10.00"},
    )
    rejected = client.post(
        f"/api/v1/debts/{debt_id}/edit-request/reject",
        headers=creditor_headers,
        json={"message": "No"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "pending_confirmation"
    assert rejected.json()["amount"] == "50.00"


def test_late_payment_penalty_doubles_per_missed_reminder(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-4", "Shop")
    debtor_headers = auth_headers("customer-4", "Omar")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)

    today = date.today()
    create = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Omar",
            "debtor_id": "customer-4",
            "amount": "30.00",
            "currency": "SAR",
            "description": "Order",
            "due_date": str(today - timedelta(days=1)),
            "reminder_dates": [str(today - timedelta(days=3)), str(today - timedelta(days=2))],
        },
    )
    debt_id = create.json()["id"]
    client.post(f"/api/v1/debts/{debt_id}/accept", headers=debtor_headers)
    # Trigger the lazy sweeper so missed reminders apply (and overdue transition runs).
    client.get("/api/v1/dashboard/debtor", headers=debtor_headers)

    # Sweeper idempotency: hitting it again must not double-charge.
    client.get("/api/v1/dashboard/debtor", headers=debtor_headers)

    client.post(f"/api/v1/debts/{debt_id}/mark-paid", headers=debtor_headers, json={"note": "late"})
    client.post(f"/api/v1/debts/{debt_id}/confirm-payment", headers=creditor_headers)

    dashboard = client.get("/api/v1/dashboard/debtor", headers=debtor_headers).json()
    # 50 base − 5 (overdue) − 2 (reminder 1) − 4 (reminder 2) − 8 (paid_late) = 31.
    assert dashboard["commitment_score"] == 31


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

