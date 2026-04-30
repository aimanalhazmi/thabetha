from __future__ import annotations

import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings
from app.schemas.domain import ProfileOut, VoiceDebtDraftOut, VoiceDraftFieldConfirmations, VoiceDraftFieldStatus

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a structured-data extractor for a bilingual (Arabic/English) debt-tracking app. "
    "Read the transcript of a creditor describing a debt and return ONLY a single JSON object "
    "with these exact keys (use null when unknown):\n"
    '  "debtor_name": string | null  // person who owes the money\n'
    '  "amount": number | null       // numeric value, no currency or thousands separators\n'
    '  "currency": string | null     // 3-letter ISO code (SAR, USD, EUR, AED, QAR, KWD, BHD, OMR). '
    'Map ر.س/ريال→SAR, دولار→USD.\n'
    '  "description": string | null  // short reason / purpose of the debt\n'
    '  "due_date": string | null     // YYYY-MM-DD when stated; otherwise null\n'
    "Do not add commentary, markdown, or extra keys. Return JSON only."
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_payload(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(cleaned)
        if not match:
            raise
        return json.loads(match.group(0))


def _coerce_amount(raw: object) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _coerce_due_date(raw: object) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _coerce_str(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _normalize_currency(value: str | None, profile: ProfileOut) -> str:
    fallback = "SAR" if profile.preferred_language == "ar" else "USD"
    if not value:
        return fallback
    lowered = value.strip().lower()
    if lowered in {"ر.س", "ريال", "sar"}:
        return "SAR"
    if lowered in {"دولار", "usd"}:
        return "USD"
    code = value.strip().upper()
    return code if len(code) == 3 and code.isalpha() else fallback


def _status(value: object | None) -> VoiceDraftFieldStatus:
    return VoiceDraftFieldStatus.extracted_unconfirmed if value not in (None, "") else VoiceDraftFieldStatus.missing


class LLMExtractionError(RuntimeError):
    """Raised when the chat-ai provider fails or returns unparsable output."""


def extract_voice_debt_draft_via_llm(*, transcript: str, profile: ProfileOut) -> VoiceDebtDraftOut:
    settings = get_settings()
    raw_transcript = transcript.strip()
    url = f"{settings.chat_ai_base_url.rstrip('/')}/chat/completions"
    api_key = settings.chat_ai_api_key or settings.openai_api_key
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": settings.chat_ai_extraction_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_transcript},
        ],
    }

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        snippet = exc.response.text[:500] if exc.response is not None else ""
        logger.warning("Extraction upstream %s returned %s: %s", url, exc.response.status_code, snippet)
        raise LLMExtractionError("chat-ai returned an error") from exc
    except Exception as exc:
        logger.warning("Extraction upstream %s failed: %r", url, exc)
        raise LLMExtractionError("chat-ai request failed") from exc

    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Extraction upstream %s returned unexpected shape: %s", url, str(data)[:500])
        raise LLMExtractionError("chat-ai response missing content") from exc

    try:
        payload = _parse_json_payload(message or "")
    except json.JSONDecodeError as exc:
        logger.warning("Extraction upstream %s returned non-JSON content: %s", url, (message or "")[:500])
        raise LLMExtractionError("chat-ai response was not valid JSON") from exc

    debtor_name = _coerce_str(payload.get("debtor_name"))
    amount = _coerce_amount(payload.get("amount"))
    currency = _normalize_currency(_coerce_str(payload.get("currency")), profile)
    description = _coerce_str(payload.get("description")) or raw_transcript or None
    due_date = _coerce_due_date(payload.get("due_date"))
    confidence = 0.9 if amount and debtor_name else 0.6 if amount or debtor_name else 0.3

    return VoiceDebtDraftOut(
        debtor_name=debtor_name,
        amount=amount,
        currency=currency,
        description=description,
        due_date=due_date,
        confidence=confidence,
        raw_transcript=raw_transcript,
        field_confirmations=VoiceDraftFieldConfirmations(
            debtor_name=_status(debtor_name),
            amount=_status(amount),
            currency=VoiceDraftFieldStatus.extracted_unconfirmed,
            description=_status(description),
            due_date=_status(due_date),
        ),
    )
