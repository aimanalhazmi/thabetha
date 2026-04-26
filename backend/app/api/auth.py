"""Auth endpoints — thin proxy to Supabase Auth for sign-up / sign-in / refresh.

The frontend calls Supabase Auth directly via @supabase/supabase-js. These
endpoints exist so server-side flows (deploys without browser SDK access) can
hit the same Supabase Auth REST surface through our backend.
"""

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings

router = APIRouter()


def _supabase_auth_url(settings: Settings) -> str:
    """Get the Supabase Auth base URL from Supabase URL."""
    base = settings.supabase_url or "http://127.0.0.1:55321"
    return f"{base}/auth/v1"


def _headers(settings: Settings) -> dict[str, str]:
    """Headers required for Supabase Auth API calls."""
    key = settings.supabase_anon_key or ""
    return {
        "apikey": key,
        "Content-Type": "application/json",
    }


@router.post("/signup")
def signup(
    payload: dict[str, Any],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Sign up via Supabase Auth. Sends verification email."""
    auth_url = _supabase_auth_url(settings)
    headers = _headers(settings)

    # Determine account type based on tax_id
    tax_id = payload.get("tax_id")
    account_type = "creditor" if tax_id else "debtor"

    body = {
        "email": payload["email"],
        "password": payload["password"],
        "data": {
            "name": payload.get("name", ""),
            "phone": payload.get("phone", ""),
            "account_type": account_type,
            "tax_id": tax_id,
            "commercial_registration": payload.get("commercial_registration"),
        },
    }

    try:
        resp = httpx.post(f"{auth_url}/signup", json=body, headers=headers, timeout=10)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Auth service unavailable: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.json().get("msg", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return resp.json()


@router.post("/signin")
def signin(
    payload: dict[str, Any],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Sign in via Supabase Auth (email + password)."""
    auth_url = _supabase_auth_url(settings)
    headers = _headers(settings)

    body = {
        "email": payload["email"],
        "password": payload["password"],
    }

    try:
        resp = httpx.post(
            f"{auth_url}/token?grant_type=password",
            json=body,
            headers=headers,
            timeout=10,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Auth service unavailable: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.json().get("error_description", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return resp.json()


@router.post("/refresh")
def refresh_token(
    payload: dict[str, Any],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Refresh tokens via Supabase Auth."""
    auth_url = _supabase_auth_url(settings)
    headers = _headers(settings)

    body = {"refresh_token": payload["refresh_token"]}

    try:
        resp = httpx.post(
            f"{auth_url}/token?grant_type=refresh_token",
            json=body,
            headers=headers,
            timeout=10,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Auth service unavailable: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()


@router.post("/signout")
def signout() -> dict[str, str]:
    return {"message": "Signed out successfully"}
