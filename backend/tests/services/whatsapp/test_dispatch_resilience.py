"""T012 — provider failure must NOT roll back the underlying transition (FR-005)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.repositories import get_repository
from app.services.whatsapp.mock import MockWhatsAppProvider
from app.services.whatsapp.provider import SendOutcome
from tests.conftest import auth_headers


def test_provider_exception_does_not_break_transition(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    creditor = auth_headers("creditor-res", "Shop")
    debtor = auth_headers("debtor-res", "Customer")
    client.get("/api/v1/profiles/me", headers=creditor)
    client.get("/api/v1/profiles/me", headers=debtor)

    # Pre-program the provider to raise on the next send (the debt_created notify).
    mock_whatsapp.set_next_exception(RuntimeError("boom"))

    resp = client.post(
        "/api/v1/debts",
        headers=creditor,
        json={
            "debtor_name": "Customer",
            "debtor_id": "debtor-res",
            "amount": "10.00",
            "currency": "SAR",
            "description": "Test",
            "due_date": str(date.today() + timedelta(days=3)),
        },
    )
    # (a) The debt transition committed.
    assert resp.status_code == 201
    debt = resp.json()
    assert debt["status"] == "pending_confirmation"

    # (b) The notification row exists (debt_created -> debtor).
    repo = get_repository()
    notifs = [n for n in repo.notifications if n.user_id == "debtor-res"]
    assert len(notifs) == 1
    notif = notifs[0]

    # (c) WhatsApp state records the failure with provider_5xx.
    state = repo.get_whatsapp_state(notif.id)
    assert state is not None
    assert state["attempted"] is True
    assert state["failed_reason"] == "provider_5xx"


def test_provider_blocked_outcome_persists_failed_reason(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    creditor = auth_headers("creditor-bk", "Shop")
    debtor = auth_headers("debtor-bk", "Customer")
    client.get("/api/v1/profiles/me", headers=creditor)
    client.get("/api/v1/profiles/me", headers=debtor)

    mock_whatsapp.set_next_outcome(SendOutcome.blocked, "recipient_blocked")
    resp = client.post(
        "/api/v1/debts",
        headers=creditor,
        json={
            "debtor_name": "Customer",
            "debtor_id": "debtor-bk",
            "amount": "10.00",
            "currency": "SAR",
            "description": "Test",
            "due_date": str(date.today() + timedelta(days=3)),
        },
    )
    assert resp.status_code == 201
    repo = get_repository()
    notif = next(n for n in repo.notifications if n.user_id == "debtor-bk")
    state = repo.get_whatsapp_state(notif.id)
    assert state["failed_reason"] == "recipient_blocked"
