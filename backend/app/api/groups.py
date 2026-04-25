from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import DebtOut, GroupCreate, GroupInviteIn, GroupMemberOut, GroupOut, SettlementCreate, SettlementOut

router = APIRouter()


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupOut:
    repo.ensure_profile(user)
    return repo.create_group(user.id, payload)


@router.get("", response_model=list[GroupOut])
def list_groups(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[GroupOut]:
    repo.ensure_profile(user)
    return repo.list_groups(user.id)


@router.post("/{group_id}/invite", response_model=GroupMemberOut)
def invite_group_member(
    group_id: str,
    payload: GroupInviteIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupMemberOut:
    repo.ensure_profile(user)
    return repo.invite_group_member(user.id, group_id, payload)


@router.post("/{group_id}/accept", response_model=GroupMemberOut)
def accept_group_invite(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupMemberOut:
    repo.ensure_profile(user)
    return repo.accept_group_invite(user.id, group_id)


@router.get("/{group_id}/debts", response_model=list[DebtOut])
def group_debts(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[DebtOut]:
    repo.ensure_profile(user)
    return repo.group_debts(user.id, group_id)


@router.post("/{group_id}/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
def create_settlement(
    group_id: str,
    payload: SettlementCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementOut:
    repo.ensure_profile(user)
    return repo.create_settlement(user.id, group_id, payload)

