from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import (
    DebtOut,
    GroupCreate,
    GroupDetailOut,
    GroupInviteIn,
    GroupMemberOut,
    GroupOut,
    GroupOwnershipTransferIn,
    GroupRenameIn,
    SettlementCreate,
    SettlementOut,
    SettlementProposalOut,
)

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


@router.get("/shared", response_model=list[GroupOut])
def shared_groups(
    with_user_id: Annotated[str, Query(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[GroupOut]:
    repo.ensure_profile(user)
    return repo.shared_accepted_groups(user.id, with_user_id)


@router.get("/{group_id}", response_model=GroupDetailOut)
def group_detail(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupDetailOut:
    repo.ensure_profile(user)
    return repo.get_group_detail(user.id, group_id)


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
def group_members(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[GroupMemberOut]:
    repo.ensure_profile(user)
    return repo.list_group_members(user.id, group_id)


@router.get("/{group_id}/invites", response_model=list[GroupMemberOut])
def list_pending_invites(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[GroupMemberOut]:
    repo.ensure_profile(user)
    return repo.list_pending_group_invites(user.id, group_id)


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


@router.post("/{group_id}/decline", response_model=GroupMemberOut)
def decline_group_invite(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupMemberOut:
    repo.ensure_profile(user)
    return repo.decline_group_invite(user.id, group_id)


@router.post("/{group_id}/leave", response_model=GroupMemberOut)
def leave_group(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupMemberOut:
    repo.ensure_profile(user)
    return repo.leave_group(user.id, group_id)


@router.post("/{group_id}/rename", response_model=GroupOut)
def rename_group(
    group_id: str,
    payload: GroupRenameIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupOut:
    repo.ensure_profile(user)
    return repo.rename_group(user.id, group_id, payload)


@router.post("/{group_id}/transfer-ownership", response_model=GroupOut)
def transfer_group_ownership(
    group_id: str,
    payload: GroupOwnershipTransferIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> GroupOut:
    repo.ensure_profile(user)
    return repo.transfer_group_ownership(user.id, group_id, payload)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> Response:
    repo.ensure_profile(user)
    repo.delete_group(user.id, group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{group_id}/invites/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_group_invite(
    group_id: str,
    target_user_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> Response:
    repo.ensure_profile(user)
    repo.revoke_group_invite(user.id, group_id, target_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/debts", response_model=list[DebtOut])
def group_debts(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[DebtOut]:
    repo.ensure_profile(user)
    return repo.group_debts(user.id, group_id)


@router.post("/{group_id}/bulk-confirm-payments", response_model=list[DebtOut])
def bulk_confirm_group_payments(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[DebtOut]:
    """Creditor confirms receipt for every payment-pending debt they are owed in this group."""
    repo.ensure_profile(user)
    return repo.bulk_confirm_group_payments(user.id, group_id)


@router.post("/{group_id}/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
def create_settlement(
    group_id: str,
    payload: SettlementCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementOut:
    repo.ensure_profile(user)
    return repo.create_settlement(user.id, group_id, payload)


# ── Settlement proposals (UC9 part 2) ──────────────────────────────────────


@router.post(
    "/{group_id}/settlement-proposals",
    response_model=SettlementProposalOut,
    status_code=status.HTTP_201_CREATED,
)
def create_settlement_proposal(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementProposalOut:
    repo.ensure_profile(user)
    return repo.create_settlement_proposal(user.id, group_id)


@router.get(
    "/{group_id}/settlement-proposals",
    response_model=list[SettlementProposalOut],
)
def list_settlement_proposals(
    group_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[SettlementProposalOut]:
    repo.ensure_profile(user)
    return repo.list_settlement_proposals(user.id, group_id, status_filter)


@router.get(
    "/{group_id}/settlement-proposals/{proposal_id}",
    response_model=SettlementProposalOut,
)
def get_settlement_proposal(
    group_id: str,
    proposal_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementProposalOut:
    repo.ensure_profile(user)
    return repo.get_settlement_proposal(user.id, group_id, proposal_id)


@router.post(
    "/{group_id}/settlement-proposals/{proposal_id}/confirm",
    response_model=SettlementProposalOut,
)
def confirm_settlement_proposal(
    group_id: str,
    proposal_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementProposalOut:
    repo.ensure_profile(user)
    return repo.confirm_settlement_proposal(user.id, group_id, proposal_id)


@router.post(
    "/{group_id}/settlement-proposals/{proposal_id}/reject",
    response_model=SettlementProposalOut,
)
def reject_settlement_proposal(
    group_id: str,
    proposal_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> SettlementProposalOut:
    repo.ensure_profile(user)
    return repo.reject_settlement_proposal(user.id, group_id, proposal_id)
