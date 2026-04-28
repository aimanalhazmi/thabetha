"""In-memory WhatsApp provider for tests and local dev.

Records every call into `MockWhatsAppProvider.calls`. Tests can pre-program the
next outcome via `set_next_outcome`. Signature verification accepts a fixed dev
secret so webhook tests are deterministic.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

from app.services.whatsapp.provider import (
    SendOutcome,
    SendRequest,
    SendResult,
    StatusUpdate,
    WhatsAppProvider,
)

DEV_WEBHOOK_SECRET = b"mock-whatsapp-dev-secret"


class MockWhatsAppProvider(WhatsAppProvider):
    def __init__(self) -> None:
        self.calls: list[SendRequest] = []
        self._next_outcome: SendOutcome | None = None
        self._next_failed_reason: str | None = None
        self._next_exception: Exception | None = None

    def reset(self) -> None:
        self.calls.clear()
        self._next_outcome = None
        self._next_failed_reason = None
        self._next_exception = None

    def set_next_outcome(self, outcome: SendOutcome, failed_reason: str | None = None) -> None:
        self._next_outcome = outcome
        self._next_failed_reason = failed_reason

    def set_next_exception(self, exc: Exception) -> None:
        self._next_exception = exc

    def send_template(self, req: SendRequest) -> SendResult:
        self.calls.append(req)
        if self._next_exception is not None:
            exc = self._next_exception
            self._next_exception = None
            raise exc
        if self._next_outcome is not None:
            outcome = self._next_outcome
            reason = self._next_failed_reason
            self._next_outcome = None
            self._next_failed_reason = None
            if outcome == SendOutcome.sent:
                return SendResult(outcome=outcome, provider_ref=f"mock-{uuid4()}")
            return SendResult(outcome=outcome, provider_ref=None, failed_reason=reason)
        return SendResult(outcome=SendOutcome.sent, provider_ref=f"mock-{uuid4()}")

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        provided = signature_header.removeprefix("sha256=")
        expected = hmac.new(DEV_WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided, expected)

    def parse_status_callback(self, payload: dict) -> list[StatusUpdate]:
        updates: list[StatusUpdate] = []
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                if change.get("field") != "messages":
                    continue
                value = change.get("value") or {}
                for status_entry in value.get("statuses", []) or []:
                    provider_ref = status_entry.get("id")
                    raw_status = status_entry.get("status")
                    if not provider_ref or raw_status not in {"sent", "delivered", "read", "failed"}:
                        continue
                    failed_reason: str | None = None
                    if raw_status == "failed":
                        errors = status_entry.get("errors") or []
                        if errors:
                            failed_reason = _map_meta_error_code(errors[0].get("code"))
                    ts = status_entry.get("timestamp")
                    occurred_at = _parse_meta_timestamp(ts)
                    updates.append(
                        StatusUpdate(
                            provider_ref=str(provider_ref),
                            status=raw_status,
                            failed_reason=failed_reason,
                            occurred_at=occurred_at,
                        )
                    )
        return updates


def _parse_meta_timestamp(ts: object) -> datetime:
    if ts is None:
        return datetime.now(UTC)
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _map_meta_error_code(code: object) -> str:
    # Minimal lookup — extend as needed when CloudAPI provider lands.
    mapping = {
        131026: "recipient_blocked",
        131047: "recipient_blocked",
        131051: "invalid_phone",
        131056: "template_param_mismatch",
        132001: "template_not_approved",
    }
    try:
        return mapping.get(int(code), "provider_4xx")  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "provider_4xx"
