"""Request-scoped database identity for RLS-backed Postgres sessions."""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import Request
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings

current_request_jwt: ContextVar[dict[str, Any] | None] = ContextVar("current_request_jwt", default=None)
current_request_info: ContextVar[dict[str, str] | None] = ContextVar("current_request_info", default=None)


def _claims_from_demo_headers(request: Request) -> dict[str, Any] | None:
    user_id = request.headers.get("x-demo-user-id")
    if not user_id:
        return None
    return {
        "sub": user_id,
        "role": "authenticated",
        "email": request.headers.get("x-demo-email"),
        "phone": request.headers.get("x-demo-phone"),
        "user_metadata": {"name": request.headers.get("x-demo-name")},
    }


def claims_from_request(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.is_production:
        demo_claims = _claims_from_demo_headers(request)
        if demo_claims is not None:
            return demo_claims

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    if settings.is_production and settings.supabase_jwt_secret:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256", "ES256"], options={"verify_aud": False})
    return jwt.decode(token, "", options={"verify_signature": False, "verify_aud": False})


def claims_json(claims: dict[str, Any]) -> str:
    return json.dumps(claims, separators=(",", ":"), sort_keys=True, default=str)


class RLSSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = current_request_jwt.set(claims_from_request(request))
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        request_id = request.headers.get("x-request-id") or str(uuid4())
        info_token = current_request_info.set({"request_id": request_id, "route": f"{request.method} {route_path}", "method": request.method})
        try:
            response = await call_next(request)
            response.headers.setdefault("x-request-id", request_id)
            return response
        finally:
            current_request_jwt.reset(token)
            current_request_info.reset(info_token)
