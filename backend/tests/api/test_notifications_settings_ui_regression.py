"""T038 — FR-015 regression: per-creditor WhatsApp preference toggle works end-to-end."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.repositories import get_repository
from app.services.whatsapp.mock import MockWhatsAppProvider
from tests.conftest import auth_headers


def _create_debt(client: TestClient, creditor_id: str, debtor_id: str) -> dict:
    resp = client.post(
        "/api/v1/debts",
        headers=auth_headers(creditor_id, "Shop"),
        json={
            "debtor_name": "Debtor",
            "debtor_id": debtor_id,
            "amount": "20.00",
            "currency": "SAR",
            "description": "regression",
            "due_date": str(date.today() + timedelta(days=5)),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _last_whatsapp_state(user_id: str) -> dict | None:
    repo = get_repository()
    matches = [n for n in reversed(repo.notifications) if n.user_id == user_id]
    if not matches:
        return None
    return repo.get_whatsapp_state(matches[0].id)


def test_per_creditor_toggle_off_suppresses_then_restores(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    """Toggle per-creditor WhatsApp off → next notification suppressed.
    Toggle back on → next notification is attempted. Verifies FR-015 + SC-007."""
    creditor = auth_headers("c-reg", "Shop")
    debtor = auth_headers("d-reg", "Customer")
    client.get("/api/v1/profiles/me", headers=creditor)
    client.get("/api/v1/profiles/me", headers=debtor)

    # Step 1: default state — send IS attempted.
    mock_whatsapp.calls.clear()
    _create_debt(client, "c-reg", "d-reg")
    assert len(mock_whatsapp.calls) == 1
    state = _last_whatsapp_state("d-reg")
    assert state is not None
    assert state["attempted"] is True

    # Step 2: debtor opts out of WhatsApp from creditor c-reg.
    resp = client.patch(
        "/api/v1/notifications/preferences",
        headers=debtor,
        json={"merchant_id": "c-reg", "whatsapp_enabled": False},
    )
    assert resp.status_code == 200

    # Trigger another notification (new debt).
    mock_whatsapp.calls.clear()
    _create_debt(client, "c-reg", "d-reg")
    assert mock_whatsapp.calls == [], "WhatsApp must be suppressed after opting out"
    state = _last_whatsapp_state("d-reg")
    assert state is None or not state.get("attempted"), "whatsapp_attempted must be False when suppressed"

    # Step 3: debtor re-enables WhatsApp for c-reg.
    resp = client.patch(
        "/api/v1/notifications/preferences",
        headers=debtor,
        json={"merchant_id": "c-reg", "whatsapp_enabled": True},
    )
    assert resp.status_code == 200

    # Trigger another notification — should be attempted again.
    mock_whatsapp.calls.clear()
    _create_debt(client, "c-reg", "d-reg")
    assert len(mock_whatsapp.calls) == 1, "WhatsApp must resume after re-enabling"
    state = _last_whatsapp_state("d-reg")
    assert state is not None
    assert state["attempted"] is True
