from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None
    phone: str | None = None
    name: str | None = None


bearer_scheme = HTTPBearer(auto_error=False)


def _demo_user_from_headers(request: Request) -> AuthenticatedUser | None:
    demo_user_id = request.headers.get("x-demo-user-id")
    if not demo_user_id:
        return None
    return AuthenticatedUser(
        id=demo_user_id,
        email=request.headers.get("x-demo-email"),
        phone=request.headers.get("x-demo-phone"),
        name=request.headers.get("x-demo-name"),
    )


def _jwks_url(settings: Settings) -> str | None:
    if settings.supabase_jwks_url:
        return settings.supabase_jwks_url
    if settings.supabase_url:
        return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return None


@lru_cache(maxsize=4)
def _fetch_jwks(url: str) -> dict[str, dict[str, Any]]:
    resp = httpx.get(url, timeout=5)
    resp.raise_for_status()
    return {k["kid"]: k for k in resp.json().get("keys", [])}


def _decode_token(token: str, settings: Settings) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            if settings.is_production:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase JWT secret is not configured")
            return jwt.get_unverified_claims(token)
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], options={"verify_aud": False})

    if alg in ("ES256", "ES384", "ES512", "RS256", "RS384", "RS512"):
        url = _jwks_url(settings)
        if not url:
            if settings.is_production:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWKS URL is not configured")
            return jwt.get_unverified_claims(token)
        try:
            keys = _fetch_jwks(url)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc
        kid = header.get("kid")
        jwk = keys.get(kid) if kid else next(iter(keys.values()), None)
        if jwk is None:
            _fetch_jwks.cache_clear()
            try:
                keys = _fetch_jwks(url)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc
            jwk = keys.get(kid) if kid else next(iter(keys.values()), None)
            if jwk is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
        return jwt.decode(token, jwk, algorithms=[alg], options={"verify_aud": False})

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    if not settings.is_production:
        demo_user = _demo_user_from_headers(request)
        if demo_user is not None:
            return demo_user

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = credentials.credentials
    try:
        claims = _decode_token(token, settings)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is missing subject")

    return AuthenticatedUser(
        id=str(user_id),
        email=claims.get("email"),
        phone=claims.get("phone"),
        name=claims.get("user_metadata", {}).get("name") if isinstance(claims.get("user_metadata"), dict) else None,
    )
