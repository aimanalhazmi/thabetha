"""T020 — preference gate enforcement on the dispatcher."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.repositories import get_repository
from app.services.whatsapp.mock import MockWhatsAppProvider
from tests.conftest import auth_headers


def _bootstrap(client: TestClient, creditor_id: str, debtor_id: str) -> None:
    client.get("/api/v1/profiles/me", headers=auth_headers(creditor_id, "Shop"))
    client.get("/api/v1/profiles/me", headers=auth_headers(debtor_id, "Customer"))


def _create_debt(client: TestClient, creditor_id: str, debtor_id: str) -> str:
    resp = client.post(
        "/api/v1/debts",
        headers=auth_headers(creditor_id, "Shop"),
        json={
            "debtor_name": "Customer",
            "debtor_id": debtor_id,
            "amount": "5.00",
            "currency": "SAR",
            "description": "T",
            "due_date": str(date.today() + timedelta(days=3)),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _last_state_for(user_id: str) -> dict | None:
    repo = get_repository()
    matches = [n for n in reversed(repo.notifications) if n.user_id == user_id]
    if not matches:
        return None
    return repo.get_whatsapp_state(matches[0].id)


def test_global_off_suppresses_send(client: TestClient, mock_whatsapp: MockWhatsAppProvider) -> None:
    _bootstrap(client, "cA", "dA")
    # Disable WhatsApp on the debtor (recipient).
    client.patch(
        "/api/v1/profiles/me",
        headers=auth_headers("dA", "Customer"),
        json={"whatsapp_enabled": False},
    )
    mock_whatsapp.calls.clear()
    _create_debt(client, "cA", "dA")
    assert mock_whatsapp.calls == []  # no provider call
    state = _last_state_for("dA")
    assert state is None or state.get("attempted") is False  # never attempted


def test_per_creditor_off_suppresses_only_that_creditor(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    _bootstrap(client, "cX", "dXY")
    _bootstrap(client, "cY", "dXY")
    # Debtor opts out of WhatsApp from creditor cX only.
    client.patch(
        "/api/v1/notifications/preferences",
        headers=auth_headers("dXY", "Customer"),
        json={"merchant_id": "cX", "whatsapp_enabled": False},
    )
    mock_whatsapp.calls.clear()
    _create_debt(client, "cX", "dXY")  # suppressed
    _create_debt(client, "cY", "dXY")  # delivered
    assert len(mock_whatsapp.calls) == 1


def test_no_preference_recorded_defaults_to_send(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    _bootstrap(client, "cZ", "dZ")
    mock_whatsapp.calls.clear()
    _create_debt(client, "cZ", "dZ")
    assert len(mock_whatsapp.calls) == 1
    state = _last_state_for("dZ")
    assert state["attempted"] is True
    assert state["provider_ref"] is not None


def test_recipient_with_no_phone_records_no_phone_number(
    client: TestClient, mock_whatsapp: MockWhatsAppProvider
) -> None:
    _bootstrap(client, "cP", "dP")
    # Strip the phone number from the debtor profile directly.
    repo = get_repository()
    profile = repo.profiles["dP"]
    repo.profiles["dP"] = profile.model_copy(update={"phone": ""})
    mock_whatsapp.calls.clear()
    _create_debt(client, "cP", "dP")
    assert mock_whatsapp.calls == []
    state = _last_state_for("dP")
    assert state["attempted"] is True
    assert state["failed_reason"] == "no_phone_number"
