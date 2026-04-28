"""Meta WhatsApp Cloud API provider.

POSTs to ``https://graph.facebook.com/v20.0/{phone_number_id}/messages`` with a
bearer token and the documented template payload. HTTP errors are translated
into the dispatcher's ``failed_reason`` codebook so the dispatcher never sees a
raw HTTP exception.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.services.whatsapp.provider import (
    SendOutcome,
    SendRequest,
    SendResult,
    StatusUpdate,
    WhatsAppProvider,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"
DEFAULT_TIMEOUT_SECONDS = 5.0


# Map Meta error codes -> dispatcher failed_reason codebook.
META_ERROR_TO_CODE: dict[int, str] = {
    131026: "recipient_blocked",
    131047: "recipient_blocked",
    131051: "invalid_phone",
    131056: "template_param_mismatch",
    132001: "template_not_approved",
    132012: "template_param_mismatch",
}


class CloudAPIWhatsAppProvider(WhatsAppProvider):
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)

    # ── send ──────────────────────────────────────────────────────────

    def send_template(self, req: SendRequest) -> SendResult:
        phone_number_id = self._settings.whatsapp_phone_number_id
        token = self._settings.whatsapp_access_token
        if not phone_number_id or not token:
            return SendResult(outcome=SendOutcome.error, provider_ref=None, failed_reason="provider_5xx")
        url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
        body = {
            "messaging_product": "whatsapp",
            "to": req.to_e164.lstrip("+"),
            "type": "template",
            "template": {
                "name": req.template_id,
                "language": {"code": req.locale},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in req.params],
                    }
                ],
            },
        }
        try:
            response = self._client.post(
                url, json=body, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.RequestError:
            logger.exception("[whatsapp.cloud_api] network error sending to %s", req.to_e164)
            return SendResult(outcome=SendOutcome.error, provider_ref=None, failed_reason="network_error")

        if response.status_code == 200:
            try:
                provider_ref = response.json()["messages"][0]["id"]
            except (KeyError, IndexError, ValueError):
                return SendResult(outcome=SendOutcome.error, provider_ref=None, failed_reason="provider_5xx")
            return SendResult(outcome=SendOutcome.sent, provider_ref=provider_ref, failed_reason=None)

        if 500 <= response.status_code < 600:
            return SendResult(outcome=SendOutcome.error, provider_ref=None, failed_reason="provider_5xx")

        # 4xx — try to map a known Meta error code, else generic.
        try:
            payload = response.json()
            code = int(payload.get("error", {}).get("code", 0))
        except (ValueError, TypeError):
            code = 0
        reason = META_ERROR_TO_CODE.get(code, "provider_4xx")
        return SendResult(outcome=SendOutcome.blocked, provider_ref=None, failed_reason=reason)

    # ── webhook ───────────────────────────────────────────────────────

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        secret = (self._settings.whatsapp_webhook_secret or "").encode()
        if not secret:
            return False
        provided = signature_header.removeprefix("sha256=")
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        try:
            return hmac.compare_digest(provided, expected)
        except (TypeError, ValueError):
            return False

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
                            try:
                                code = int(errors[0].get("code", 0))
                            except (TypeError, ValueError):
                                code = 0
                            failed_reason = META_ERROR_TO_CODE.get(code, "provider_4xx")
                    occurred_at = _parse_meta_timestamp(status_entry.get("timestamp"))
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
