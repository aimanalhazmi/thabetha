"""Integration tests for POST /api/v1/debts/{id}/pay-online (Phase 4 — US1)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.repositories.memory import InMemoryRepository
from app.schemas.domain import DebtStatus
from app.services.payments import reset_provider_cache

from .conftest import auth_headers


@pytest.fixture(autouse=True)
def reset_payment_cache() -> None:
    reset_provider_cache()


def _make_active_debt(client: TestClient, creditor_id: str, debtor_id: str, amount: str = "100.00") -> dict:
    resp = client.post(
        "/api/v1/debts",
        json={
            "debtor_name": "Debtor",
            "debtor_id": debtor_id,
            "amount": amount,
            "currency": "SAR",
            "description": "Test",
            "due_date": "2099-12-31",
        },
        headers=auth_headers(creditor_id),
    )
    assert resp.status_code == 201
    debt = resp.json()
    resp = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=auth_headers(debtor_id))
    assert resp.status_code == 200
    return resp.json()


def test_pay_online_success_returns_200_and_checkout_url(client: TestClient) -> None:
    debt = _make_active_debt(client, "c1", "d1")
    resp = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d1"))
    assert resp.status_code == 200
    body = resp.json()
    assert "checkout_url" in body
    assert body["checkout_url"]


def test_pay_online_transitions_debt_to_payment_pending(client: TestClient) -> None:
    debt = _make_active_debt(client, "c2", "d2")
    client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d2"))
    resp = client.get(f"/api/v1/debts/{debt['id']}", headers=auth_headers("d2"))
    assert resp.json()["status"] == DebtStatus.payment_pending_confirmation


def test_pay_online_writes_payment_initiated_event(client: TestClient) -> None:
    debt = _make_active_debt(client, "c3", "d3")
    client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d3"))
    events = client.get(f"/api/v1/debts/{debt['id']}/events", headers=auth_headers("d3")).json()
    assert any(e["event_type"] == "payment_initiated" for e in events)


def test_pay_online_fee_accuracy(client: TestClient) -> None:
    """SC-004: fee and net_amount in response match provider.calculate_fee()."""
    debt = _make_active_debt(client, "c4", "d4", amount="200.00")
    resp = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d4"))
    body = resp.json()
    from decimal import Decimal
    amount = Decimal(body["amount"])
    fee = Decimal(body["fee"])
    net = Decimal(body["net_amount"])
    # Mock provider returns fee=0
    assert fee == Decimal("0")
    assert net == amount - fee


def test_pay_online_creditor_forbidden(client: TestClient) -> None:
    debt = _make_active_debt(client, "c5", "d5")
    resp = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("c5"))
    assert resp.status_code == 403


def test_pay_online_wrong_state_paid_returns_409(client: TestClient, reset_repository: InMemoryRepository) -> None:
    debt = _make_active_debt(client, "c6", "d6")
    # Mark paid via manual path
    client.post(f"/api/v1/debts/{debt['id']}/mark-paid", json={}, headers=auth_headers("d6"))
    client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=auth_headers("c6"))
    resp = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d6"))
    assert resp.status_code == 409


def test_pay_online_wrong_state_payment_pending_returns_409(client: TestClient) -> None:
    debt = _make_active_debt(client, "c7", "d7")
    client.post(f"/api/v1/debts/{debt['id']}/mark-paid", json={}, headers=auth_headers("d7"))
    resp = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d7"))
    assert resp.status_code == 409


def test_pay_online_pending_intent_blocks_second_attempt(client: TestClient) -> None:
    """FR-012: second pay-online call while intent pending returns 409 (debt in payment_pending_confirmation)."""
    debt = _make_active_debt(client, "c8", "d8")
    first = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d8"))
    assert first.status_code == 200
    # Debt is now payment_pending_confirmation; second call is rejected by state check.
    second = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d8"))
    assert second.status_code == 409


def test_pay_online_expired_intent_allows_retry(client: TestClient, reset_repository: InMemoryRepository) -> None:
    """FR-012: an expired intent allows a new pay-online attempt."""
    debt = _make_active_debt(client, "c9", "d9")
    # Force debt back to active since mark-paid doesn't use pay-online
    first = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d9"))
    assert first.status_code == 200

    # Force-expire the intent
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])
    from app.schemas.domain import utcnow
    from datetime import timedelta
    reset_repository.payment_intents[pi.id] = pi.model_copy(
        update={"expires_at": utcnow() - timedelta(minutes=1)}
    )
    # Force debt back to active/overdue so pay-online can run
    existing_debt = reset_repository.debts[debt["id"]]
    reset_repository.debts[debt["id"]] = existing_debt.model_copy(update={"status": DebtStatus.active})

    second = client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("d9"))
    assert second.status_code == 200
