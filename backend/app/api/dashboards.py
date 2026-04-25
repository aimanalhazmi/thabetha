from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories.memory import InMemoryRepository, get_repository
from app.schemas.domain import CreditorDashboardOut, DebtorDashboardOut

router = APIRouter()


@router.get("/debtor", response_model=DebtorDashboardOut)
def debtor_dashboard(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> DebtorDashboardOut:
    repo.ensure_profile(user)
    return repo.debtor_dashboard(user.id)


@router.get("/creditor", response_model=CreditorDashboardOut)
def creditor_dashboard(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[InMemoryRepository, Depends(get_repository)],
) -> CreditorDashboardOut:
    repo.ensure_profile(user)
    return repo.creditor_dashboard(user.id)

