"""WhatsApp Business API integration package.

Provider factory + module entry point. Implementation modules:
- provider.py: ABC + dataclasses
- mock.py: in-memory provider for tests/dev
- cloud_api.py: Meta Graph API provider (production)
- templates.py: NotificationType -> template registry
- dispatch.py: orchestrator (preferences -> template -> provider -> persist)
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.whatsapp.provider import WhatsAppProvider


@lru_cache(maxsize=1)
def get_provider() -> WhatsAppProvider:
    settings = get_settings()
    name = (settings.whatsapp_provider or "mock").lower()
    if name == "cloud_api":
        from app.services.whatsapp.cloud_api import CloudAPIWhatsAppProvider

        return CloudAPIWhatsAppProvider(settings)
    from app.services.whatsapp.mock import MockWhatsAppProvider

    return MockWhatsAppProvider()


def reset_provider_cache() -> None:
    """Test hook — drop the memoised provider so a fresh instance is built."""
    get_provider.cache_clear()
