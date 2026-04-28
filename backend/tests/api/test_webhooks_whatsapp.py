"""T023 — webhook handler tests."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.repositories import get_repository
from app.services.whatsapp.mock import DEV_WEBHOOK_SECRET, MockWhatsAppProvider
from tests.conftest import auth_headers


def _signed(body: dict) -> tuple[bytes, str]:
    raw = json.dumps(body).encode()
    sig = hmac.new(DEV_WEBHOOK_SECRET, raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={sig}"


def _create_one_debt(client: TestClient) -> str:
    client.get("/api/v1/profiles/me", headers=auth_headers("c-wh", "Shop"))
    client.get("/api/v1/profiles/me", headers=auth_headers("d-wh", "Customer"))
    resp = client.post(
        "/api/v1/debts",
        headers=auth_headers("c-wh", "Shop"),
        json={
            "debtor_name": "Customer",
            "debtor_id": "d-wh",
            "amount": "5.00",
            "currency": "SAR",
            "description": "T",
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _provider_ref_for_debtor() -> str:
    repo = get_repository()
    notif = next(n for n in repo.notifications if n.user_id == "d-wh")
    state = repo.get_whatsapp_state(notif.id)
    return state["provider_ref"]


def test_signature_valid_applies_status(client: TestClient, mock_whatsapp: MockWhatsAppProvider) -> None:
    _create_one_debt(client)
    ref = _provider_ref_for_debtor()
    body = {
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [
            {"id": ref, "status": "delivered", "timestamp": "1714291200"},
        ]}}]}]
    }
    raw, sig = _signed(body)
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True, "applied": 1}
    repo = get_repository()
    notif = next(n for n in repo.notifications if n.user_id == "d-wh")
    state = repo.get_whatsapp_state(notif.id)
    assert state["delivered"] is True


def test_signature_invalid_returns_403(client: TestClient) -> None:
    body = {"entry": []}
    raw = json.dumps(body).encode()
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_signature_missing_returns_403(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        content=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_unknown_provider_ref_is_noop(client: TestClient) -> None:
    body = {
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [
            {"id": "wamid.unknown", "status": "delivered", "timestamp": "1714291200"},
        ]}}]}]
    }
    raw, sig = _signed(body)
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True, "applied": 0}


def test_duplicate_callback_idempotent(client: TestClient) -> None:
    _create_one_debt(client)
    ref = _provider_ref_for_debtor()
    body = {
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [
            {"id": ref, "status": "delivered", "timestamp": "1714291200"},
        ]}}]}]
    }
    raw, sig = _signed(body)
    headers = {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}
    client.post("/api/v1/webhooks/whatsapp", content=raw, headers=headers)
    second = client.post("/api/v1/webhooks/whatsapp", content=raw, headers=headers)
    assert second.status_code == 200
    repo = get_repository()
    notif = next(n for n in repo.notifications if n.user_id == "d-wh")
    state = repo.get_whatsapp_state(notif.id)
    assert state["delivered"] is True


def test_failed_after_delivered_is_noop(client: TestClient) -> None:
    _create_one_debt(client)
    ref = _provider_ref_for_debtor()
    delivered = {
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [
            {"id": ref, "status": "delivered", "timestamp": "1714291200"},
        ]}}]}]
    }
    raw, sig = _signed(delivered)
    client.post(
        "/api/v1/webhooks/whatsapp", content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    failed = {
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [
            {"id": ref, "status": "failed", "timestamp": "1714291201", "errors": [{"code": 131026}]},
        ]}}]}]
    }
    raw2, sig2 = _signed(failed)
    client.post(
        "/api/v1/webhooks/whatsapp", content=raw2,
        headers={"X-Hub-Signature-256": sig2, "Content-Type": "application/json"},
    )
    repo = get_repository()
    notif = next(n for n in repo.notifications if n.user_id == "d-wh")
    state = repo.get_whatsapp_state(notif.id)
    assert state["delivered"] is True
    assert state["failed_reason"] is None  # not downgraded


def test_get_verification_handshake_ok_and_403(client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_verify_token", "expected-token")
    ok = client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "expected-token", "hub.challenge": "12345"},
    )
    assert ok.status_code == 200
    assert ok.text == "12345"

    bad = client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
    )
    assert bad.status_code == 403
