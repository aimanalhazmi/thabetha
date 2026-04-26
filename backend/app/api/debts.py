from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import (
    ActionMessageIn,
    AttachmentOut,
    AttachmentType,
    DebtCreate,
    DebtEditRequest,
    DebtEventOut,
    DebtOut,
    PaymentConfirmationOut,
    PaymentRequest,
)

router = APIRouter()


@router.post("", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
def create_debt(
    payload: DebtCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.create_debt(user.id, payload)


@router.get("", response_model=list[DebtOut])
def list_debts(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[DebtOut]:
    repo.ensure_profile(user)
    return repo.list_debts_for_user(user.id)


@router.get("/{debt_id}", response_model=DebtOut)
def get_debt(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.get_authorized_debt(user.id, debt_id)


@router.get("/{debt_id}/events", response_model=list[DebtEventOut])
def get_debt_events(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[DebtEventOut]:
    repo.ensure_profile(user)
    return repo.list_events(user.id, debt_id)


@router.post("/{debt_id}/accept", response_model=DebtOut)
def accept_debt(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.accept_debt(user.id, debt_id)


@router.post("/{debt_id}/reject", response_model=DebtOut)
def reject_debt(
    debt_id: str,
    payload: ActionMessageIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.reject_debt(user.id, debt_id, payload.message)


@router.post("/{debt_id}/edit-request", response_model=DebtOut)
def request_edit(
    debt_id: str,
    payload: DebtEditRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.request_debt_change(user.id, debt_id, payload)


@router.post("/{debt_id}/cancel", response_model=DebtOut)
def cancel_debt(
    debt_id: str,
    payload: ActionMessageIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.cancel_debt(user.id, debt_id, payload.message)


@router.post("/{debt_id}/mark-paid", response_model=PaymentConfirmationOut)
def mark_paid(
    debt_id: str,
    payload: PaymentRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> PaymentConfirmationOut:
    repo.ensure_profile(user)
    return repo.mark_paid(user.id, debt_id, payload)


@router.post("/{debt_id}/confirm-payment", response_model=DebtOut)
def confirm_payment(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> DebtOut:
    repo.ensure_profile(user)
    return repo.confirm_payment(user.id, debt_id)


@router.post("/{debt_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
    file: Annotated[UploadFile, File()],
    attachment_type: Annotated[AttachmentType, Query()] = AttachmentType.other,
) -> AttachmentOut:
    repo.ensure_profile(user)
    return await repo.add_attachment(user.id, debt_id, attachment_type, file)


@router.get("/{debt_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    debt_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[AttachmentOut]:
    repo.ensure_profile(user)
    return repo.list_attachments(user.id, debt_id)
