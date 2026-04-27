from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.schemas.domain import AttachmentRetentionState, AttachmentOut, DebtOut, DebtStatus, utcnow


def receipt_url_expires_at(now: datetime | None = None) -> datetime:
    now = _aware(now or utcnow())
    return now + timedelta(seconds=get_settings().receipt_signed_url_ttl_seconds)


def retention_for_debt(debt: DebtOut, now: datetime | None = None) -> tuple[AttachmentRetentionState, datetime | None]:
    if debt.status != DebtStatus.paid or debt.paid_at is None:
        return AttachmentRetentionState.available, None

    expires_at = _add_months(_aware(debt.paid_at), get_settings().receipt_archive_retention_months)
    if _aware(now or utcnow()) > expires_at:
        return AttachmentRetentionState.retention_expired, expires_at
    return AttachmentRetentionState.archived, expires_at


def apply_attachment_access_metadata(attachment: AttachmentOut, debt: DebtOut, url: str | None = None) -> AttachmentOut:
    retention_state, retention_expires_at = retention_for_debt(debt)
    return attachment.model_copy(
        update={
            "url": url or attachment.url,
            "url_expires_at": receipt_url_expires_at(),
            "retention_state": retention_state,
            "retention_expires_at": retention_expires_at,
        }
    )


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
