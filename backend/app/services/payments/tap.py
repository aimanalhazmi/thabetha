"""Tap payment provider (production)."""
from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.services.payments.provider import CheckoutSession, PaymentProvider, WebhookPaymentEvent

_TAP_API_BASE = "https://api.tap.company/v2"


class TapPaymentProvider(PaymentProvider):
    def create_checkout(
        self,
        debt_id: str,
        amount: Decimal,
        currency: str,
        redirect_url: str,
        order_ref: str,
    ) -> CheckoutSession:
        settings = get_settings()
        payload = {
            "amount": float(amount),
            "currency": currency,
            "reference": {"order": order_ref},
            "redirect": {"url": redirect_url},
            "post": {"url": redirect_url},
        }
        resp = httpx.post(
            f"{_TAP_API_BASE}/charges",
            json=payload,
            headers={"Authorization": f"Bearer {settings.tap_secret_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return CheckoutSession(
            checkout_url=data["transaction"]["url"],
            provider_ref=data["id"],
            fee=self.calculate_fee(amount),
        )

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        settings = get_settings()
        if not settings.tap_webhook_secret:
            return False
        expected = hmac.new(
            key=settings.tap_webhook_secret.encode(),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def parse_webhook_event(self, raw_body: bytes) -> WebhookPaymentEvent:
        data = json.loads(raw_body)
        raw_status = data.get("status", "")
        status = "succeeded" if raw_status == "CAPTURED" else "failed"
        return WebhookPaymentEvent(
            provider_ref=data["id"],
            status=status,
            amount=Decimal(str(data.get("amount", "0"))),
            fee=Decimal(str(data.get("fee", "0"))),
        )

    def calculate_fee(self, amount: Decimal) -> Decimal:
        settings = get_settings()
        return Decimal(str(round(float(amount) * settings.tap_fee_percent / 100, 2)))
