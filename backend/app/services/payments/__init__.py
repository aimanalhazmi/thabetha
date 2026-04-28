"""Payment gateway integration package.

Provider factory + module entry point. Implementation modules:
- provider.py: ABC + dataclasses (CheckoutSession, WebhookPaymentEvent)
- mock.py: in-memory provider for tests/dev
- tap.py: Tap Cloud API provider (production — stub until T029)
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.payments.provider import PaymentProvider


@lru_cache(maxsize=1)
def get_payment_provider() -> PaymentProvider:
    name = (get_settings().payment_provider or "mock").lower()
    if name == "tap":
        from app.services.payments.tap import TapPaymentProvider

        return TapPaymentProvider()
    if name == "mock":
        from app.services.payments.mock import MockPaymentProvider

        return MockPaymentProvider()
    raise ValueError(f"Unknown PAYMENT_PROVIDER: {name!r}. Valid values: 'mock', 'tap'")


def reset_provider_cache() -> None:
    """Test hook — drop the memoised provider so a fresh instance is built."""
    get_payment_provider.cache_clear()
