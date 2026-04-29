from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.schemas.domain import ProfileOut, VoiceDebtDraftOut, VoiceDraftFieldConfirmations, VoiceDraftFieldStatus

_CURRENCY_PATTERN = re.compile(r"\b(SAR|USD|EUR|AED|QAR|KWD|BHD|OMR|ر\.س|ريال|دولار)\b", re.IGNORECASE)
_AMOUNT_PATTERN = re.compile(r"(\d+(?:[.,]\d{1,2})?)")
_DUE_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_DEBTOR_PATTERN = re.compile(r"(?:على|for|from)\s+([\w\u0600-\u06FF ]{2,30}?)(?=\s+\d|\s+(?:SAR|USD|ريال|due)\b|$)", re.IGNORECASE)


def _currency_from_locale(profile: ProfileOut) -> str:
    return "SAR" if profile.preferred_language == "ar" else "USD"


def _normalize_currency(value: str | None, profile: ProfileOut) -> str:
    if not value:
        return _currency_from_locale(profile)
    lowered = value.lower()
    if lowered in {"ر.س", "ريال"}:
        return "SAR"
    if lowered == "دولار":
        return "USD"
    return value.upper()


def _parse_amount(transcript: str) -> Decimal | None:
    transcript_without_dates = _DUE_DATE_PATTERN.sub(" ", transcript)
    match = _AMOUNT_PATTERN.search(transcript_without_dates)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None


def _parse_due_date(transcript: str) -> date | None:
    match = _DUE_DATE_PATTERN.search(transcript)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _parse_debtor_name(transcript: str) -> str | None:
    match = _DEBTOR_PATTERN.search(transcript)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _status(value: object | None) -> VoiceDraftFieldStatus:
    return VoiceDraftFieldStatus.extracted_unconfirmed if value is not None and value != "" else VoiceDraftFieldStatus.missing


def extract_voice_debt_draft(*, transcript: str, profile: ProfileOut) -> VoiceDebtDraftOut:
    raw_transcript = transcript.strip()
    amount = _parse_amount(raw_transcript)
    due_date = _parse_due_date(raw_transcript)
    debtor_name = _parse_debtor_name(raw_transcript)
    currency_match = _CURRENCY_PATTERN.search(raw_transcript)
    currency = _normalize_currency(currency_match.group(1) if currency_match else None, profile)
    description = raw_transcript or None
    confidence = 0.85 if amount and debtor_name else 0.45 if amount else 0.2
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
