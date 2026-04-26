from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import BusinessProfileIn, BusinessProfileOut, ProfileOut, ProfileUpdate, TrustScoreEventOut

router = APIRouter()


@router.get("/me", response_model=ProfileOut)
def get_me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> ProfileOut:
    return repo.ensure_profile(user)


@router.patch("/me", response_model=ProfileOut)
def update_me(
    payload: ProfileUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> ProfileOut:
    return repo.update_profile(user, payload)


@router.post("/business-profile", response_model=BusinessProfileOut, status_code=201)
def upsert_business_profile(
    payload: BusinessProfileIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> BusinessProfileOut:
    repo.ensure_profile(user)
    return repo.upsert_business_profile(user.id, payload)


@router.get("/business-profile", response_model=BusinessProfileOut | None)
def get_business_profile(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> BusinessProfileOut | None:
    repo.ensure_profile(user)
    return repo.current_business_profile(user.id)


@router.get("/me/trust-score-events", response_model=list[TrustScoreEventOut])
def list_trust_score_events(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> list[TrustScoreEventOut]:
    repo.ensure_profile(user)
    return repo.list_trust_score_events(user.id)

