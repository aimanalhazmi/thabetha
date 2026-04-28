"""Integration tests for the canonical happy path and edit-request branch (Phase 4 — e2e demo polish)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _setup_users(client: TestClient, creditor_id: str = "creditor-demo", debtor_id: str = "debtor-demo") -> tuple[dict, dict]:
    """Ensure both demo profiles exist and return their auth headers."""
    cred = auth_headers(creditor_id, "Demo Creditor")
    deb = auth_headers(debtor_id, "Demo Debtor")
    client.get("/api/v1/profiles/me", headers=cred)
    client.get("/api/v1/profiles/me", headers=deb)
    return cred, deb


def _create_debt(client: TestClient, cred_headers: dict, debtor_id: str, due_offset_days: int = 2) -> dict:
    resp = client.post(
        "/api/v1/debts",
        headers=cred_headers,
        json={
            "debtor_name": "Demo Debtor",
            "debtor_id": debtor_id,
            "amount": "100.00",
            "currency": "SAR",
            "description": "Demo purchase",
            "due_date": str(date.today() + timedelta(days=due_offset_days)),
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_canonical_happy_path(client: TestClient) -> None:
    """
    Full happy-path lifecycle: create → accept → mark-paid → confirm-payment.
    Asserts exact status-transition sequence and commitment-score delta (+3 early).
    """
    cred, deb = _setup_users(client)
    debtor_id = "debtor-demo"

    # Step 1: Create debt
    debt = _create_debt(client, cred, debtor_id)
    assert debt["status"] == "pending_confirmation"

    # Step 2: Debtor accepts
    accepted = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=deb)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    # Step 3: Debtor marks paid
    payment = client.post(
        f"/api/v1/debts/{debt['id']}/mark-paid",
        headers=deb,
        json={"note": "Paid via demo"},
    )
    assert payment.status_code == 200
    assert payment.json()["status"] == "pending_creditor_confirmation"

    # Step 4: Creditor confirms
    confirmed = client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=cred)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"

    # Step 5: Commitment score — paid before due_date → +3 (early-payment bonus)
    dashboard = client.get("/api/v1/dashboard/debtor", headers=deb)
    assert dashboard.status_code == 200
    assert dashboard.json()["commitment_score"] == 53


def test_edit_request_branch(client: TestClient) -> None:
    """
    Edit-request branch: create → request-edit → approve → accept → mark-paid → confirm.
    Asserts the additional edit_requested state and that new terms are applied.
    Final commitment-score delta is still +3 (paid before due_date).
    """
    cred, deb = _setup_users(client, creditor_id="creditor-demo2", debtor_id="debtor-demo2")
    debtor_id = "debtor-demo2"

    # Step 1: Create debt
    debt = _create_debt(client, cred, debtor_id)
    assert debt["status"] == "pending_confirmation"

    # Step 2: Debtor requests edit (proposed amount: 80 SAR)
    edit_req = client.post(
        f"/api/v1/debts/{debt['id']}/edit-request",
        headers=deb,
        json={"message": "Please reduce amount", "requested_amount": "80.00"},
    )
    assert edit_req.status_code == 200
    assert edit_req.json()["status"] == "edit_requested"

    # Step 3: Creditor approves with the proposed terms
    approved = client.post(
        f"/api/v1/debts/{debt['id']}/edit-request/approve",
        headers=cred,
        json={"message": "Approved, updated amount", "requested_amount": "80.00"},
    )
    assert approved.status_code == 200
    approved_debt = approved.json()
    assert approved_debt["status"] == "pending_confirmation"
    assert approved_debt["amount"] == "80.00"

    # Step 4: Debtor accepts the new terms
    accepted = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=deb)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    # Step 5: Debtor marks paid
    payment = client.post(
        f"/api/v1/debts/{debt['id']}/mark-paid",
        headers=deb,
        json={"note": "Paid updated amount"},
    )
    assert payment.status_code == 200
    assert payment.json()["status"] == "pending_creditor_confirmation"

    # Step 6: Creditor confirms
    confirmed = client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=cred)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"

    # Step 7: Commitment score — paid before due_date → +3
    dashboard = client.get("/api/v1/dashboard/debtor", headers=deb)
    assert dashboard.status_code == 200
    assert dashboard.json()["commitment_score"] == 53
