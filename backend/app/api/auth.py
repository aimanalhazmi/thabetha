"""Auth endpoints — sign-up / sign-in with bcrypt password hashing and HS256 JWTs."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from psycopg.rows import dict_row

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser
from app.repositories import Repository, get_repository
from app.schemas.domain import RefreshRequest, SignInRequest, SignUpRequest

router = APIRouter()

_ACCESS_EXPIRE = timedelta(hours=1)
_REFRESH_EXPIRE = timedelta(days=7)
_ALGORITHM = "HS256"


def _make_access_token(user_id: str, email: str, name: str, phone: str, secret: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "phone": phone,
        "user_metadata": {"name": name, "phone": phone},
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + _ACCESS_EXPIRE).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _make_refresh_token(user_id: str, secret: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": int((now + _REFRESH_EXPIRE).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _require_secret(settings: Settings) -> str:
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret is not configured (SUPABASE_JWT_SECRET)")
    return settings.supabase_jwt_secret


def _require_pool(repo: Repository):
    from app.repositories.postgres import PostgresRepository

    if not isinstance(repo, PostgresRepository):
        raise HTTPException(status_code=503, detail="Auth requires REPOSITORY_TYPE=postgres")
    return repo._pool


@router.post("/signup")
def signup(
    payload: SignUpRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> dict[str, Any]:
    secret = _require_secret(settings)
    pool = _require_pool(repo)

    pw_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())

    with pool.connection() as conn:
        try:
            conn.execute(
                "INSERT INTO public.users (id, email, password_hash, name, phone) VALUES (%s, %s, %s, %s, %s)",
                (user_id, payload.email, pw_hash, payload.name, payload.phone),
            )
            conn.commit()
        except Exception as exc:
            msg = str(exc).lower()
            if "unique" in msg or "duplicate" in msg:
                raise HTTPException(status_code=422, detail="Email already registered") from exc
            raise

    # Create profile row via repository
    auth_user = AuthenticatedUser(id=user_id, name=payload.name, phone=payload.phone, email=payload.email)
    repo.ensure_profile(auth_user)

    if payload.account_type.value == "business" or payload.tax_id or payload.commercial_registration:
        from app.schemas.domain import ProfileUpdate

        repo.update_profile(
            auth_user,
            ProfileUpdate(
                account_type=payload.account_type,
                tax_id=payload.tax_id,
                commercial_registration=payload.commercial_registration,
            ),
        )

    access_token = _make_access_token(user_id, payload.email, payload.name, payload.phone, secret)
    refresh_token = _make_refresh_token(user_id, secret)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(_ACCESS_EXPIRE.total_seconds()),
        "user": {
            "id": user_id,
            "email": payload.email,
            "user_metadata": {"name": payload.name, "phone": payload.phone},
        },
    }


@router.post("/signin")
def signin(
    payload: SignInRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> dict[str, Any]:
    secret = _require_secret(settings)
    pool = _require_pool(repo)

    with pool.connection() as conn:
        conn.row_factory = dict_row
        row = conn.execute(
            "SELECT id, email, password_hash, name, phone FROM public.users WHERE email = %s",
            (payload.email,),
        ).fetchone()

    if row is None or not bcrypt.checkpw(payload.password.encode(), row["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = str(row["id"])
    name = row["name"] or ""
    phone = row["phone"] or ""

    access_token = _make_access_token(user_id, payload.email, name, phone, secret)
    refresh_token = _make_refresh_token(user_id, secret)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(_ACCESS_EXPIRE.total_seconds()),
        "user": {
            "id": user_id,
            "email": payload.email,
            "user_metadata": {"name": name, "phone": phone},
        },
    }


@router.post("/refresh")
def refresh_token(
    payload: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> dict[str, Any]:
    secret = _require_secret(settings)
    pool = _require_pool(repo)

    try:
        claims = jwt.decode(payload.refresh_token, secret, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with pool.connection() as conn:
        conn.row_factory = dict_row
        row = conn.execute(
            "SELECT email, name, phone FROM public.users WHERE id = %s",
            (user_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = _make_access_token(user_id, row["email"], row["name"] or "", row["phone"] or "", secret)
    new_refresh = _make_refresh_token(user_id, secret)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": int(_ACCESS_EXPIRE.total_seconds()),
    }


@router.post("/signout")
def signout() -> dict[str, str]:
    return {"message": "Signed out successfully"}
