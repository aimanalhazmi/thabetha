"""Mock payment provider for dev/test — no real network calls."""
from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.services.payments.provider import CheckoutSession, PaymentProvider, WebhookPaymentEvent


class MockPaymentProvider(PaymentProvider):
    def create_checkout(
        self,
        debt_id: str,
        amount: Decimal,
        currency: str,
        redirect_url: str,
        order_ref: str,
    ) -> CheckoutSession:
        base = get_settings().payment_redirect_base_url
        return CheckoutSession(
            checkout_url=f"{base}/payment/mock-return?ref={order_ref}&debt_id={debt_id}",
            provider_ref=str(uuid4()),
            fee=Decimal("0"),
        )

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        # Mock always accepts; real signature check is Tap-specific
        return True

    def parse_webhook_event(self, raw_body: bytes) -> WebhookPaymentEvent:
        payload = json.loads(raw_body)
        raw_status = payload.get("status", "CAPTURED")
        status = "succeeded" if raw_status == "CAPTURED" else "failed"
        return WebhookPaymentEvent(
            provider_ref=payload["id"],
            status=status,
            amount=Decimal(str(payload.get("amount", "0"))),
            fee=Decimal(str(payload.get("fee", "0"))),
        )

    def calculate_fee(self, amount: Decimal) -> Decimal:
        return Decimal("0")
