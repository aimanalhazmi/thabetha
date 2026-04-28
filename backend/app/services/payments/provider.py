"""Payment provider ABC and shared dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CheckoutSession:
    checkout_url: str
    provider_ref: str
    fee: Decimal


@dataclass
class WebhookPaymentEvent:
    provider_ref: str
    # normalised status: 'succeeded' | 'failed'
    status: str
    amount: Decimal
    fee: Decimal


class PaymentProvider(ABC):
    @abstractmethod
    def create_checkout(
        self,
        debt_id: str,
        amount: Decimal,
        currency: str,
        redirect_url: str,
        order_ref: str,
    ) -> CheckoutSession: ...

    @abstractmethod
    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool: ...

    @abstractmethod
    def parse_webhook_event(self, raw_body: bytes) -> WebhookPaymentEvent: ...

    @abstractmethod
    def calculate_fee(self, amount: Decimal) -> Decimal: ...
