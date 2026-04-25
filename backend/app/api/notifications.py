from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories.memory import InMemoryRepository, get_repository
from app.schemas.domain import NotificationOut, NotificationPreferenceIn, NotificationPreferenceOut

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> list[NotificationOut]:
    repo.ensure_profile(user)
    return repo.list_notifications(user.id)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> NotificationOut:
    repo.ensure_profile(user)
    return repo.read_notification(user.id, notification_id)


@router.patch("/preferences", response_model=NotificationPreferenceOut)
def set_notification_preference(
    payload: NotificationPreferenceIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> NotificationPreferenceOut:
    repo.ensure_profile(user)
    return repo.set_notification_preference(user.id, payload)

