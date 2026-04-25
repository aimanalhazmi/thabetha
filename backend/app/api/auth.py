"""Auth endpoints — proxy sign-up / sign-in to GoTrue (Supabase Auth)."""

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser
from app.repositories import Repository, get_repository
from app.schemas.domain import RefreshRequest, SignInRequest, SignUpRequest

router = APIRouter()


def _gotrue_url(settings: Settings) -> str:
    if not settings.gotrue_url:
        raise HTTPException(status_code=500, detail="Auth service is not configured (GOTRUE_URL)")
    return settings.gotrue_url


@router.post("/signup")
async def signup(
    payload: SignUpRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> dict[str, Any]:
    base = _gotrue_url(settings)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base}/signup",
            json={
                "email": payload.email,
                "password": payload.password,
                "data": {
                    "name": payload.name,
                    "phone": payload.phone,
                    "account_type": payload.account_type.value,
                },
            },
            timeout=10,
        )

    if resp.status_code >= 400:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    data = resp.json()

    # Create profile row in our profiles table
    user_id = data.get("id") or data.get("user", {}).get("id")
    if user_id:
        repo.ensure_profile(
            AuthenticatedUser(
                id=str(user_id),
                name=payload.name,
                phone=payload.phone,
                email=payload.email,
            )
        )
        # Update optional business fields
        if payload.tax_id or payload.commercial_registration or payload.account_type == "business":
            from app.schemas.domain import ProfileUpdate

            repo.update_profile(
                AuthenticatedUser(id=str(user_id), name=payload.name, phone=payload.phone, email=payload.email),
                ProfileUpdate(
                    account_type=payload.account_type,
                    tax_id=payload.tax_id,
                    commercial_registration=payload.commercial_registration,
                ),
            )

    return data


@router.post("/signin")
async def signin(
    payload: SignInRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    base = _gotrue_url(settings)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base}/token?grant_type=password",
            json={"email": payload.email, "password": payload.password},
            timeout=10,
        )

    if resp.status_code >= 400:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return resp.json()


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    base = _gotrue_url(settings)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base}/token?grant_type=refresh_token",
            json={"refresh_token": payload.refresh_token},
            timeout=10,
        )

    if resp.status_code >= 400:
        detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return resp.json()


@router.post("/signout")
async def signout() -> dict[str, str]:
    return {"message": "Signed out successfully"}
