from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

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
        if settings.is_production:
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase JWT secret is not configured")
            claims = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256", "ES256"], options={"verify_aud": False})
        else:
            claims = jwt.decode(token, "", options={"verify_signature": False, "verify_aud": False})
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid bearer token: {str(exc)}") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is missing subject")

    return AuthenticatedUser(
        id=str(user_id),
        email=claims.get("email"),
        phone=claims.get("phone"),
        name=claims.get("user_metadata", {}).get("name") if isinstance(claims.get("user_metadata"), dict) else None,
    )


