"""WhatsApp send orchestrator.

`dispatch_notification(notification, repo, provider, *, recipient_id, sender_id,
payload)` is invoked **after** an in-app notification row has been committed.
The dispatcher MUST never raise — provider failures are recorded on the
notification row so the underlying business transition is never affected.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.schemas.domain import NotificationOut, NotificationType, ProfileOut
from app.services.whatsapp.provider import (
    SendOutcome,
    SendRequest,
    SendResult,
    WhatsAppProvider,
)
from app.services.whatsapp.templates import pick_template

if TYPE_CHECKING:
    from app.repositories.base import Repository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DispatchContext:
    """Inputs the dispatcher needs that are not on `NotificationOut` itself."""

    recipient: ProfileOut
    sender_id: str | None  # creditor for debtor-facing messages; None for system messages
    creditor_id: str | None  # populated when the message is from creditor -> debtor
    debtor_id: str | None
    template_params: dict[str, str]


def _failed(reason: str) -> SendResult:
    return SendResult(outcome=SendOutcome.blocked, provider_ref=None, failed_reason=reason)


def dispatch_notification(
    notification: NotificationOut,
    ctx: DispatchContext,
    repo: Repository,
    provider: WhatsAppProvider,
) -> SendResult | None:
    """Run the dispatch algorithm. Returns the SendResult that was persisted, or
    None when the message was suppressed by a preference gate (i.e. attempted
    stays False)."""
    try:
        # 1. Global recipient toggle.
        if not getattr(ctx.recipient, "whatsapp_enabled", True):
            logger.info(
                "[whatsapp.dispatch] suppressed reason=global_off user=%s notification=%s",
                ctx.recipient.id,
                notification.id,
            )
            return None

        # 2. Per-creditor opt-out (only meaningful when creditor -> debtor).
        if ctx.creditor_id and ctx.debtor_id and ctx.recipient.id == ctx.debtor_id:
            preference = repo.get_merchant_notification_preference(ctx.creditor_id, ctx.debtor_id)
            if preference is not None and not preference.whatsapp_enabled:
                logger.info(
                    "[whatsapp.dispatch] suppressed reason=per_creditor_opt_out user=%s creditor=%s",
                    ctx.recipient.id,
                    ctx.creditor_id,
                )
                return None

        # 3. Phone gate.
        phone = (ctx.recipient.phone or "").strip()
        if not phone:
            result = _failed("no_phone_number")
            repo.mark_whatsapp_attempted(notification.id, result)
            return result

        # 4. Template lookup with locale fallback.
        chosen = pick_template(notification.notification_type, ctx.recipient.preferred_language)
        if chosen is None:
            result = _failed("no_template")
            repo.mark_whatsapp_attempted(notification.id, result)
            return result
        template_id, locale, params_layout = chosen

        # 5. Build positional params.
        params = [ctx.template_params.get(key, "") for key in params_layout]

        # 6. Provider call.
        try:
            result = provider.send_template(
                SendRequest(to_e164=phone, template_id=template_id, locale=locale, params=params)
            )
        except Exception:  # noqa: BLE001 — never let provider errors escape.
            logger.exception(
                "[whatsapp.dispatch] provider raised notification=%s", notification.id
            )
            result = SendResult(outcome=SendOutcome.error, provider_ref=None, failed_reason="provider_5xx")

        repo.mark_whatsapp_attempted(notification.id, result)
        return result
    except Exception:  # noqa: BLE001 — last-resort safety net.
        logger.exception(
            "[whatsapp.dispatch] unexpected error notification=%s", notification.id
        )
        return None


def build_default_template_params(
    *,
    creditor_name: str | None,
    debtor_name: str | None,
    amount: str | None,
    currency: str | None,
    debt_link: str | None,
    due_date: str | None,
) -> dict[str, str]:
    return {
        "creditor_name": creditor_name or "",
        "debtor_name": debtor_name or "",
        "amount": amount or "",
        "currency": currency or "",
        "debt_link": debt_link or "",
        "due_date": due_date or "",
    }


__all__ = [
    "DispatchContext",
    "dispatch_notification",
    "build_default_template_params",
    "NotificationType",
]
