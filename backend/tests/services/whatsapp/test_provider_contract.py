"""T011 — provider contract tests against MockWhatsAppProvider."""
from __future__ import annotations

import hashlib
import hmac

import pytest

from app.services.whatsapp.mock import DEV_WEBHOOK_SECRET, MockWhatsAppProvider
from app.services.whatsapp.provider import SendOutcome, SendRequest


@pytest.fixture
def provider() -> MockWhatsAppProvider:
    return MockWhatsAppProvider()


def _req() -> SendRequest:
    return SendRequest(to_e164="+966500000000", template_id="debt_created_ar", locale="ar", params=["a", "b"])


def test_send_template_default_returns_sent(provider: MockWhatsAppProvider) -> None:
    result = provider.send_template(_req())
    assert result.outcome == SendOutcome.sent
    assert result.provider_ref and result.provider_ref.startswith("mock-")
    assert result.failed_reason is None
    assert provider.calls == [_req()]


def test_send_template_blocked_outcome(provider: MockWhatsAppProvider) -> None:
    provider.set_next_outcome(SendOutcome.blocked, "recipient_blocked")
    result = provider.send_template(_req())
    assert result.outcome == SendOutcome.blocked
    assert result.provider_ref is None
    assert result.failed_reason == "recipient_blocked"


def test_send_template_error_outcome(provider: MockWhatsAppProvider) -> None:
    provider.set_next_outcome(SendOutcome.error, "provider_5xx")
    result = provider.send_template(_req())
    assert result.outcome == SendOutcome.error
    assert result.failed_reason == "provider_5xx"


def test_verify_webhook_signature_valid(provider: MockWhatsAppProvider) -> None:
    body = b'{"hello":"world"}'
    sig = hmac.new(DEV_WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    assert provider.verify_webhook_signature(body, f"sha256={sig}") is True
    assert provider.verify_webhook_signature(body, sig) is True  # prefix optional


def test_verify_webhook_signature_invalid(provider: MockWhatsAppProvider) -> None:
    assert provider.verify_webhook_signature(b"x", "sha256=deadbeef") is False
    assert provider.verify_webhook_signature(b"x", "") is False


def test_parse_status_callback_shape(provider: MockWhatsAppProvider) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [
                                {"id": "wamid.A", "status": "delivered", "timestamp": "1714291200"},
                                {
                                    "id": "wamid.B",
                                    "status": "failed",
                                    "timestamp": "1714291201",
                                    "errors": [{"code": 131026}],
                                },
                            ]
                        },
                    }
                ]
            }
        ]
    }
    updates = provider.parse_status_callback(payload)
    assert [u.provider_ref for u in updates] == ["wamid.A", "wamid.B"]
    assert updates[0].status == "delivered"
    assert updates[1].status == "failed"
    assert updates[1].failed_reason == "recipient_blocked"
