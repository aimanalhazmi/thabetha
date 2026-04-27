"""Integration tests: QR-scanner pass-through — create debt linked via debtor_id.

Covers T006 (US1 happy path) and T018a (self-billing 409 guard).
Uses REPOSITORY_TYPE=memory and demo auth headers per the constitution.
"""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_create_debt_via_qr_debtor_id(client: TestClient) -> None:
    """Happy path: creditor resolves debtor QR then creates a debt linked by debtor_id."""
    creditor_h = auth_headers("creditor-qr-1", "Saqr Shop", "+966500000010")
    debtor_h = auth_headers("debtor-qr-1", "Fahad Customer", "+966500000011")

    # Ensure both profiles exist
    client.get("/api/v1/profiles/me", headers=creditor_h)
    client.get("/api/v1/profiles/me", headers=debtor_h)

    # Creditor gets debtor's QR token (as if debtor displayed it)
    qr_resp = client.get("/api/v1/qr/current", headers=debtor_h)
    assert qr_resp.status_code == 200
    token = qr_resp.json()["token"]

    # Creditor resolves the token
    resolve_resp = client.get(f"/api/v1/qr/resolve/{token}", headers=creditor_h)
    assert resolve_resp.status_code == 200
    resolved_profile = resolve_resp.json()
    assert resolved_profile["id"] == "debtor-qr-1"

    # Creditor creates debt with both debtor_id (from resolve) and debtor_name
    create_resp = client.post(
        "/api/v1/debts",
        headers=creditor_h,
        json={
            "debtor_name": resolved_profile["name"],
            "debtor_id": resolved_profile["id"],
            "amount": "150.00",
            "currency": "SAR",
            "description": "Groceries — QR linked",
            "due_date": "2026-06-01",
        },
    )
    assert create_resp.status_code == 201
    debt = create_resp.json()
    assert debt["debtor_id"] == "debtor-qr-1", "Debt must carry the resolved debtor_id"
    assert debt["status"] == "pending_confirmation"

    debt_id = debt["id"]

    # Debtor can see the debt in their list
    debtor_debts = client.get("/api/v1/debts", headers=debtor_h)
    assert debtor_debts.status_code == 200
    debtor_debt_ids = [d["id"] for d in debtor_debts.json()]
    assert debt_id in debtor_debt_ids, "Debtor must see the QR-linked debt in their list"


def test_create_debt_self_billing_blocked(client: TestClient) -> None:
    """T018a: creating a debt where debtor_id == creditor user_id must return 409."""
    user_h = auth_headers("self-bill-user-1", "Solo User", "+966500000020")

    client.get("/api/v1/profiles/me", headers=user_h)

    resp = client.post(
        "/api/v1/debts",
        headers=user_h,
        json={
            "debtor_name": "Solo User",
            "debtor_id": "self-bill-user-1",  # same as the authenticated user
            "amount": "50.00",
            "currency": "SAR",
            "description": "Self-billing attempt",
            "due_date": "2026-06-01",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "cannot_bill_self"
