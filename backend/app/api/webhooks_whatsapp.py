"""WhatsApp webhook router.

Endpoints:
- ``POST /webhooks/whatsapp``: signed delivery callbacks from Meta. Verifies
  ``X-Hub-Signature-256`` then idempotently applies parsed status updates.
- ``GET /webhooks/whatsapp``: Meta subscription handshake.

Neither endpoint depends on Supabase Auth — Meta calls them with a shared HMAC
secret (POST) or a verify token (GET).
"""
from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings
from app.repositories import Repository, get_repository
from app.schemas.domain import WebhookReceiptOut
from app.services.whatsapp import get_provider
from app.services.whatsapp.dispatch import verify_whatsapp_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhooks/whatsapp")
def verify_subscription(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Response:
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")
    expected = settings.whatsapp_verify_token
    if mode == "subscribe" and expected and token == expected:
        return Response(content=challenge, media_type="text/plain", status_code=200)
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@router.post("/webhooks/whatsapp", response_model=WebhookReceiptOut)
async def receive_status(
    request: Request,
    repo: Annotated[Repository, Depends(get_repository)],
) -> WebhookReceiptOut:
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_whatsapp_signature(raw, signature):
        # Structured audit log — never log the body (PII).
        logger.warning(
            "[whatsapp.webhook] signature_rejected signature_present=%s body_len=%d "
            "user_agent=%r remote=%s",
            bool(signature),
            len(raw),
            request.headers.get("user-agent", ""),
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc

    provider = get_provider()
    updates = provider.parse_status_callback(payload)
    applied = 0
    for update in updates:
        try:
            if repo.apply_whatsapp_status(update):
                applied += 1
                logger.info(
                    "[whatsapp.webhook] applied provider_ref=%s status=%s",
                    update.provider_ref,
                    update.status,
                )
            else:
                logger.info(
                    "[whatsapp.webhook] unknown_ref provider_ref=%s status=%s applied=0",
                    update.provider_ref,
                    update.status,
                )
        except Exception:  # noqa: BLE001
            logger.exception(
                "[whatsapp.webhook] db_error provider_ref=%s",
                update.provider_ref,
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None
    return WebhookReceiptOut(received=True, applied=applied)
