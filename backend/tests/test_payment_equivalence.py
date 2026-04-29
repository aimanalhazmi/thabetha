"""SC-003: Manual confirm and gateway webhook paths produce identical outcomes (Phase 6 — US4)."""
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


def _setup_debt(client: TestClient, creditor_id: str, debtor_id: str) -> dict:
    resp = client.post(
        "/api/v1/debts",
        json={
            "debtor_name": "Debtor",
            "debtor_id": debtor_id,
            "amount": "50.00",
            "currency": "SAR",
            "description": "Equivalence test debt",
            "due_date": "2099-12-31",
        },
        headers=auth_headers(creditor_id),
    )
    assert resp.status_code == 201
    debt = resp.json()
    resp = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=auth_headers(debtor_id))
    assert resp.status_code == 200
    return resp.json()


def test_sc003_manual_and_gateway_paths_produce_identical_event_schema(
    client: TestClient, reset_repository: InMemoryRepository
) -> None:
    """SC-003: Both paths write a payment_confirmed event with the same event_type."""
    # Manual path
    debt_manual = _setup_debt(client, "cm1", "dm1")
    client.post(f"/api/v1/debts/{debt_manual['id']}/mark-paid", json={}, headers=auth_headers("dm1"))
    client.post(f"/api/v1/debts/{debt_manual['id']}/confirm-payment", headers=auth_headers("cm1"))

    # Gateway path
    debt_gw = _setup_debt(client, "cm2", "dm2")
    client.post(f"/api/v1/debts/{debt_gw['id']}/pay-online", headers=auth_headers("dm2"))
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt_gw["id"])
    payload = json.dumps({"id": pi.provider_ref, "status": "CAPTURED"}).encode()
    client.post(
        "/api/v1/webhooks/payments",
        content=payload,
        headers={"Content-Type": "application/json", "X-Payment-Signature": "mock"},
    )

    # Both debts must be paid
    assert client.get(f"/api/v1/debts/{debt_manual['id']}", headers=auth_headers("cm1")).json()["status"] == DebtStatus.paid
    assert client.get(f"/api/v1/debts/{debt_gw['id']}", headers=auth_headers("cm2")).json()["status"] == DebtStatus.paid

    # Both must have a payment_confirmed event
    events_manual = client.get(f"/api/v1/debts/{debt_manual['id']}/events", headers=auth_headers("cm1")).json()
    events_gw = client.get(f"/api/v1/debts/{debt_gw['id']}/events", headers=auth_headers("cm2")).json()

    confirmed_manual = [e for e in events_manual if e["event_type"] == "payment_confirmed"]
    confirmed_gw = [e for e in events_gw if e["event_type"] == "payment_confirmed"]

    assert len(confirmed_manual) == 1, "Manual path must write exactly one payment_confirmed event"
    assert len(confirmed_gw) == 1, "Gateway path must write exactly one payment_confirmed event"
    assert confirmed_manual[0]["event_type"] == confirmed_gw[0]["event_type"]


def test_sc003_commitment_score_delta_identical(
    client: TestClient, reset_repository: InMemoryRepository
) -> None:
    """SC-003: Both paths produce the same commitment score delta (both paid early)."""
    debt_manual = _setup_debt(client, "cs1", "ds1")
    debt_gw = _setup_debt(client, "cs2", "ds2")

    # Manual confirm
    client.post(f"/api/v1/debts/{debt_manual['id']}/mark-paid", json={}, headers=auth_headers("ds1"))
    client.post(f"/api/v1/debts/{debt_manual['id']}/confirm-payment", headers=auth_headers("cs1"))

    # Gateway confirm
    client.post(f"/api/v1/debts/{debt_gw['id']}/pay-online", headers=auth_headers("ds2"))
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt_gw["id"])
    payload = json.dumps({"id": pi.provider_ref, "status": "CAPTURED"}).encode()
    client.post(
        "/api/v1/webhooks/payments",
        content=payload,
        headers={"Content-Type": "application/json", "X-Payment-Signature": "mock"},
    )

    # Verify both debtors received the same commitment score delta (paid early → +3)
    events_manual = [e for e in reset_repository.commitment_score_events if e.user_id == "ds1"]
    events_gw = [e for e in reset_repository.commitment_score_events if e.user_id == "ds2"]

    assert events_manual, "Manual path must produce a commitment score event"
    assert events_gw, "Gateway path must produce a commitment score event"

    delta_manual = events_manual[-1].delta
    delta_gw = events_gw[-1].delta
    assert delta_manual == delta_gw, f"Deltas must match: manual={delta_manual}, gateway={delta_gw}"


def test_us4_creditor_cannot_confirm_already_gateway_paid_debt(
    client: TestClient, reset_repository: InMemoryRepository
) -> None:
    """US4 acceptance scenario 2: creditor cannot manually confirm a gateway-paid debt."""
    debt = _setup_debt(client, "cv1", "dv1")

    # Pay via gateway
    client.post(f"/api/v1/debts/{debt['id']}/pay-online", headers=auth_headers("dv1"))
    pi = next(pi for pi in reset_repository.payment_intents.values() if pi.debt_id == debt["id"])
    payload = json.dumps({"id": pi.provider_ref, "status": "CAPTURED"}).encode()
    client.post(
        "/api/v1/webhooks/payments",
        content=payload,
        headers={"Content-Type": "application/json", "X-Payment-Signature": "mock"},
    )

    # Creditor tries to confirm again → 409
    resp = client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=auth_headers("cv1"))
    assert resp.status_code == 409
