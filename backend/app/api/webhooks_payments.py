"""Payment gateway webhook router.

POST /webhooks/payments — receives signed callbacks from the payment gateway.
Verifies HMAC signature, parses event, and updates debt/intent state atomically.
No Supabase Auth — gated by shared HMAC secret instead.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.repositories import Repository, get_repository
from app.schemas.domain import WebhookReceiptOut
from app.services.payments import get_payment_provider

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/payments", response_model=WebhookReceiptOut)
async def receive_payment_webhook(
    request: Request,
    repo: Annotated[Repository, Depends(get_repository)],
) -> WebhookReceiptOut:
    raw = await request.body()
    signature = request.headers.get("X-Payment-Signature", "")

    provider = get_payment_provider()

    if not provider.verify_signature(raw, signature):
        logger.warning(
            "[payment.webhook] signature_rejected signature_present=%s body_len=%d remote=%s",
            bool(signature),
            len(raw),
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    try:
        event = provider.parse_webhook_event(raw)
    except Exception as exc:
        logger.exception("[payment.webhook] parse_failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc

    try:
        if event.status == "succeeded":
            repo.confirm_payment_gateway(event.provider_ref)
            logger.info("[payment.webhook] confirmed provider_ref=%s", event.provider_ref)
        else:
            repo.record_payment_failure(event.provider_ref)
            logger.info("[payment.webhook] failed provider_ref=%s status=%s", event.provider_ref, event.status)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[payment.webhook] processing_error provider_ref=%s", event.provider_ref)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

    return WebhookReceiptOut(received=True, applied=1)
