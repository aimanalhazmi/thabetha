"""WhatsAppProvider ABC + value types.

Mirror of `specs/006-whatsapp-business-integration/contracts/whatsapp_provider.md`.
Both `MockWhatsAppProvider` and `CloudAPIWhatsAppProvider` MUST satisfy this
contract identically so the dispatcher and tests are provider-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

Locale = Literal["ar", "en"]


class SendOutcome(StrEnum):
    sent = "sent"
    blocked = "blocked"
    error = "error"


# Failure codebook — keep in lockstep with frontend i18n keys (T031).
FAILED_REASONS: frozenset[str] = frozenset(
    {
        "recipient_blocked",
        "invalid_phone",
        "template_not_approved",
        "template_param_mismatch",
        "provider_4xx",
        "provider_5xx",
        "network_error",
        "no_template",
        "no_phone_number",
    }
)


@dataclass(frozen=True, slots=True)
class SendRequest:
    to_e164: str
    template_id: str
    locale: Locale
    params: list[str]


@dataclass(frozen=True, slots=True)
class SendResult:
    outcome: SendOutcome
    provider_ref: str | None = None
    failed_reason: str | None = None


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    provider_ref: str
    status: Literal["sent", "delivered", "read", "failed"]
    failed_reason: str | None
    occurred_at: datetime


class WhatsAppProvider(ABC):
    @abstractmethod
    def send_template(self, req: SendRequest) -> SendResult: ...

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool: ...

    @abstractmethod
    def parse_status_callback(self, payload: dict) -> list[StatusUpdate]: ...
