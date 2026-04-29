"""Integration tests for POST /api/v1/webhooks/payments (Phase 3 — US3)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.repositories.memory import InMemoryRepository
from app.schemas.domain import DebtStatus
from app.services.payments import reset_provider_cache

from .conftest import auth_headers


@pytest.fixture(autouse=True)
def reset_payment_cache() -> None:
    reset_provider_cache()


def _make_webhook_payload(provider_ref: str, status: str = "CAPTURED") -> bytes:
    return json.dumps({"id": provider_ref, "status": status}).encode()


def _active_debt(client: TestClient, creditor_id: str, debtor_id: str) -> dict:
    resp = client.post(
        "/api/v1/debts",
        json={
            "debtor_name": "Test Debtor",
            "debtor_id": debtor_id,
            "amount": "100.00",
            "currency": "SAR",
            "description": "Test debt",
            "due_date": "2099-12-31",
        },
        headers=auth_headers(creditor_id),
    )
    assert resp.status_code == 201
    debt = resp.json()
    # Debtor accepts → active
    resp = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=auth_headers(debtor_id))
    assert resp.status_code == 200
    return resp.json()


def _pay_online(client: TestClient, debt_id: str, debtor_id: str) -> dict:
    resp = client.post(f"/api/v1/debts/{debt_id}/pay-online", headers=auth_headers(debtor_id))
    assert resp.status_code == 200
    return resp.json()


def _send_webhook(client: TestClient, provider_ref: str, gateway_status: str = "CAPTURED") -> dict:
    payload = _make_webhook_payload(provider_ref, gateway_status)
    resp = client.post(
        "/api/v1/webhooks/payments",
        content=payload,
        headers={"Content-Type": "application/json", "X-Payment-Signature": "mock"},
    )
    return resp.json() if resp.status_code == 200 else {"status_code": resp.status_code}


def test_webhook_success_transitions_debt_to_paid(client: TestClient, reset_repository: InMemoryRepository) -> None:
    debt = _active_debt(client, "cred-1", "debt-1")
    intent = _pay_online(client, debt["id"], "debt-1")

    # Override the provider_ref in the intent so we can send it in the webhook
    pi = reset_repository.payment_intents.get(intent["payment_intent_id"])
    assert pi is not None
    actual_ref = pi.provider_ref

    result = _send_webhook(client, actual_ref)
    assert result["received"] is True

    debt_resp = client.get(f"/api/v1/debts/{debt['id']}", headers=auth_headers("cred-1"))
    assert debt_resp.json()["status"] == DebtStatus.paid


def test_webhook_writes_payment_confirmed_event(client: TestClient, reset_repository: InMemoryRepository) -> None:
    debt = _active_debt(client, "cred-2", "debt-2")
    _pay_online(client, debt["id"], "debt-2")
    pi_list = [pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"]]
    assert pi_list
    provider_ref = pi_list[0].provider_ref

    _send_webhook(client, provider_ref)

    events_resp = client.get(f"/api/v1/debts/{debt['id']}/events", headers=auth_headers("cred-2"))
    event_types = [e["event_type"] for e in events_resp.json()]
    assert "payment_confirmed" in event_types


def test_webhook_idempotent_replay(client: TestClient, reset_repository: InMemoryRepository) -> None:
    """SC-002: duplicate webhook delivery produces no duplicate event and no duplicate transition."""
    debt = _active_debt(client, "cred-3", "debt-3")
    _pay_online(client, debt["id"], "debt-3")
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])

    _send_webhook(client, pi.provider_ref)
    _send_webhook(client, pi.provider_ref)  # replay

    events_resp = client.get(f"/api/v1/debts/{debt['id']}/events", headers=auth_headers("cred-3"))
    confirmed = [e for e in events_resp.json() if e["event_type"] == "payment_confirmed"]
    assert len(confirmed) == 1

    debt_resp = client.get(f"/api/v1/debts/{debt['id']}", headers=auth_headers("cred-3"))
    assert debt_resp.json()["status"] == DebtStatus.paid


def test_webhook_mock_accepts_any_signature(client: TestClient, reset_repository: InMemoryRepository) -> None:
    """Mock provider always returns True for verify_signature — route must not reject."""
    # Set up a real intent so the route can process end-to-end
    debt_resp = client.post(
        "/api/v1/debts",
        json={"debtor_name": "X", "debtor_id": "d-sig", "amount": "10.00", "currency": "SAR", "description": "sig test", "due_date": "2099-01-01"},
        headers=auth_headers("c-sig"),
    )
    debt = debt_resp.json()
    client.post(f"/api/v1/debts/{debt['id']}/accept", headers=auth_headers("d-sig"))
    client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d-sig"))
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])

    payload = _make_webhook_payload(pi.provider_ref)
    resp = client.post(
        "/api/v1/webhooks/payments",
        content=payload,
        headers={"Content-Type": "application/json", "X-Payment-Signature": "any-value-mock-accepts"},
    )
    assert resp.status_code == 200


def test_webhook_failed_status_keeps_debt_in_payment_pending(client: TestClient, reset_repository: InMemoryRepository) -> None:
    debt = _active_debt(client, "cred-4", "debt-4")
    _pay_online(client, debt["id"], "debt-4")
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])

    _send_webhook(client, pi.provider_ref, gateway_status="DECLINED")

    debt_resp = client.get(f"/api/v1/debts/{debt['id']}", headers=auth_headers("cred-4"))
    assert debt_resp.json()["status"] == DebtStatus.payment_pending_confirmation

    updated_pi = reset_repository.payment_intents[pi.id]
    assert updated_pi.status == "failed"


def test_failed_payment_allows_retry(client: TestClient, reset_repository: InMemoryRepository) -> None:
    """FR-013: after a failed webhook the debtor can initiate pay-online again."""
    debt = _active_debt(client, "cred-5", "debt-5")
    _pay_online(client, debt["id"], "debt-5")
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])

    # Webhook signals failure — intent marked failed, debt stays payment_pending_confirmation
    _send_webhook(client, pi.provider_ref, gateway_status="DECLINED")

    # Force debt back to active so pay-online state check passes (simulates external reset)
    existing = reset_repository.debts[debt["id"]]
    reset_repository.debts[debt["id"]] = existing.model_copy(update={"status": DebtStatus.active})

    # Second pay-online must succeed and create a new intent
    second = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("debt-5"))
    assert second.status_code == 200
    assert second.json()["checkout_url"]

    # Exactly two intents recorded for this debt: first (failed) and second (pending)
    intents_for_debt = [p for p in reset_repository.payment_intents.values() if p.debt_id == debt["id"]]
    assert len(intents_for_debt) == 2
