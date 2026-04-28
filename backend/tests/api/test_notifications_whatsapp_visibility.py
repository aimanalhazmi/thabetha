"""T024 — debtors do NOT see WhatsApp delivery columns; creditors DO (Q1)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.repositories import get_repository
from tests.conftest import auth_headers


def _bootstrap(client: TestClient) -> str:
    creditor = auth_headers("creditor-vis", "Shop")
    debtor = auth_headers("debtor-vis", "Customer")
    # Creditor must register as a business profile to be tagged as creditor.
    client.get("/api/v1/profiles/me", headers=creditor)
    client.patch(
        "/api/v1/profiles/me",
        headers=creditor,
        json={"account_type": "creditor"},
    )
    client.get("/api/v1/profiles/me", headers=debtor)
    resp = client.post(
        "/api/v1/debts",
        headers=creditor,
        json={
            "debtor_name": "Customer",
            "debtor_id": "debtor-vis",
            "amount": "5.00",
            "currency": "SAR",
            "description": "T",
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_debtor_view_excludes_delivery_columns(client: TestClient) -> None:
    _bootstrap(client)
    resp = client.get("/api/v1/notifications", headers=auth_headers("debtor-vis", "Customer"))
    assert resp.status_code == 200
    rows = resp.json()
    assert rows
    for row in rows:
        assert "whatsapp_delivered" not in row
        assert "whatsapp_failed_reason" not in row
        assert "whatsapp_status" not in row
        assert "whatsapp_attempted" in row  # legacy field still present


def test_creditor_view_includes_delivery_columns(client: TestClient) -> None:
    debt_id = _bootstrap(client)
    # Trigger a creditor-facing notification by accepting the debt.
    accept = client.post(
        f"/api/v1/debts/{debt_id}/accept",
        headers=auth_headers("debtor-vis", "Customer"),
    )
    assert accept.status_code == 200

    resp = client.get("/api/v1/notifications", headers=auth_headers("creditor-vis", "Shop"))
    assert resp.status_code == 200
    rows = resp.json()
    assert rows
    for row in rows:
        assert "whatsapp_status" in row
        assert "whatsapp_delivered" in row
        assert "whatsapp_failed_reason" in row

    # And the underlying state is sane.
    repo = get_repository()
    creditor_notifs = [n for n in repo.notifications if n.user_id == "creditor-vis"]
    assert creditor_notifs
    state = repo.get_whatsapp_state(creditor_notifs[0].id)
    assert state["attempted"] is True
