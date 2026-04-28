from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import (
    AccountType,
    NotificationOut,
    NotificationOutCreditor,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    derive_whatsapp_status,
)

router = APIRouter()

CREDITOR_ACCOUNT_TYPES = {AccountType.creditor, AccountType.business, AccountType.both}


def _project_notification(
    notification: NotificationOut, repo: Repository, *, as_creditor: bool
) -> NotificationOut | NotificationOutCreditor:
    """Project the right response shape per Q1.

    Creditors / business users see ``NotificationOutCreditor`` with the
    WhatsApp delivery columns; debtors see the plain ``NotificationOut``.
    """
    if not as_creditor:
        return notification
    state = repo.get_whatsapp_state(notification.id) or {}
    attempted = bool(state.get("attempted", notification.whatsapp_attempted))
    delivered = state.get("delivered")
    failed_reason = state.get("failed_reason")
    status_received_at = state.get("status_received_at")
    return NotificationOutCreditor(
        **notification.model_dump(),
        whatsapp_delivered=delivered if isinstance(delivered, bool) else None,
        whatsapp_failed_reason=failed_reason if isinstance(failed_reason, str) else None,
        whatsapp_status=derive_whatsapp_status(
            whatsapp_attempted=attempted,
            whatsapp_delivered=delivered if isinstance(delivered, bool) else None,
            whatsapp_failed_reason=failed_reason if isinstance(failed_reason, str) else None,
        ),
        whatsapp_status_received_at=status_received_at if hasattr(status_received_at, "isoformat") else None,
    )


@router.get("")
def list_notifications(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[dict]:
    profile = repo.ensure_profile(user)
    as_creditor = profile.account_type in CREDITOR_ACCOUNT_TYPES
    rows = repo.list_notifications(user.id)
    return [
        _project_notification(n, repo, as_creditor=as_creditor).model_dump(mode="json")
        for n in rows
    ]


@router.post("/{notification_id}/read")
def read_notification(
    notification_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> dict:
    profile = repo.ensure_profile(user)
    as_creditor = profile.account_type in CREDITOR_ACCOUNT_TYPES
    notification = repo.read_notification(user.id, notification_id)
    return _project_notification(notification, repo, as_creditor=as_creditor).model_dump(mode="json")


@router.patch("/preferences", response_model=NotificationPreferenceOut)
def set_notification_preference(
    payload: NotificationPreferenceIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> NotificationPreferenceOut:
    repo.ensure_profile(user)
    return repo.set_notification_preference(user.id, payload)

