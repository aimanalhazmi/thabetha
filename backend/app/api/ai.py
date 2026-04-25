import re
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories.memory import InMemoryRepository, get_repository
from app.schemas.domain import MerchantChatOut, MerchantChatRequest, VoiceDebtDraftOut, VoiceDebtDraftRequest

router = APIRouter()


def _require_ai_enabled(user: AuthenticatedUser, repo: InMemoryRepository) -> None:
    profile = repo.ensure_profile(user)
    if not profile.ai_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI features require an active AI subscription")


@router.post("/debt-draft-from-voice", response_model=VoiceDebtDraftOut)
def draft_debt_from_voice(
    payload: VoiceDebtDraftRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> VoiceDebtDraftOut:
    _require_ai_enabled(user, repo)
    transcript = payload.transcript.strip()
    amount_match = re.search(r"(\d+(?:[.,]\d{1,2})?)", transcript)
    amount = Decimal(amount_match.group(1).replace(",", ".")) if amount_match else None
    debtor_match = re.search(r"(?:على|for|from)\s+([\w\u0600-\u06FF ]{2,30})", transcript, re.IGNORECASE)
    debtor_name = debtor_match.group(1).strip() if debtor_match else None
    due_date_match = re.search(r"(\d{4}-\d{2}-\d{2})", transcript)
    parsed_due_date = date.fromisoformat(due_date_match.group(1)) if due_date_match else None
    confidence = 0.85 if amount and debtor_name else 0.45 if amount else 0.2
    return VoiceDebtDraftOut(
        debtor_name=debtor_name,
        amount=amount,
        currency=payload.default_currency.upper(),
        description=transcript,
        due_date=parsed_due_date,
        confidence=confidence,
        raw_transcript=transcript,
    )


@router.post("/merchant-chat", response_model=MerchantChatOut)
def merchant_chat(
    payload: MerchantChatRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> MerchantChatOut:
    _require_ai_enabled(user, repo)
    facts = repo.merchant_facts(user.id)
    answer = (
        f"You have {facts['active_count']} active debts, {facts['overdue_count']} overdue debts, "
        f"and total receivables of {facts['total_receivable']}. "
        f"Recommendation: follow up on overdue customers first and keep QR confirmation for new debts."
    )
    if "متأخر" in payload.message or "overdue" in payload.message.lower():
        answer = f"Overdue summary: {facts['overdue_count']} debts need attention. Alerts: {facts['alerts'] or ['No overdue alerts.']}"
    return MerchantChatOut(answer=answer, facts=facts)

