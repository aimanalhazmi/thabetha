from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.repositories import Repository

VOICE_DRAFT_FEATURE = "voice_debt_draft"
MERCHANT_CHAT_FEATURE = "merchant_chat"

_DAILY_LIMIT_FIELDS = {
    VOICE_DRAFT_FEATURE: "ai_voice_draft_daily_limit",
    MERCHANT_CHAT_FEATURE: "ai_merchant_chat_daily_limit",
}


def _daily_limit_for(feature: str) -> int:
    settings = get_settings()
    field = _DAILY_LIMIT_FIELDS.get(feature, "ai_voice_draft_daily_limit")
    return int(getattr(settings, field))


def retry_after_seconds(today: date | None = None) -> int:
    current = today or date.today()
    tomorrow = datetime.combine(current + timedelta(days=1), time.min)
    return max(1, int((tomorrow - datetime.now()).total_seconds()))


def ensure_ai_quota_available(repo: Repository, user_id: str, feature: str = VOICE_DRAFT_FEATURE) -> None:
    usage_date = date.today()
    limit = _daily_limit_for(feature)
    count = repo.get_ai_usage_count(user_id, feature, usage_date)
    if count >= limit:
        message = "Daily merchant-chat limit reached" if feature == MERCHANT_CHAT_FEATURE else "Daily AI draft limit reached"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "ai_daily_limit_reached", "message": message},
            headers={"Retry-After": str(retry_after_seconds(usage_date))},
        )


def record_ai_usage(repo: Repository, user_id: str, feature: str = VOICE_DRAFT_FEATURE) -> int:
    return repo.increment_ai_usage(user_id, feature, date.today(), _daily_limit_for(feature))
