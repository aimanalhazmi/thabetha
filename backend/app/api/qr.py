from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import ProfileOut, QRTokenOut

router = APIRouter()


@router.get("/current", response_model=QRTokenOut)
def current_qr(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> QRTokenOut:
    repo.ensure_profile(user)
    return QRTokenOut(**repo.current_qr_token(user.id))


@router.post("/rotate", response_model=QRTokenOut)
def rotate_qr(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> QRTokenOut:
    repo.ensure_profile(user)
    return QRTokenOut(**repo.rotate_qr_token(user.id))


@router.get("/resolve/{token}", response_model=ProfileOut)
def resolve_qr(
    token: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> ProfileOut:
    repo.ensure_profile(user)
    return repo.resolve_qr_token(token)

