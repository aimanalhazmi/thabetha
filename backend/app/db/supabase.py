from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client | None:
    settings = get_settings()
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        return None
    return create_client(settings.supabase_url, key)


def supabase_available() -> bool:
    return get_supabase_client() is not None


def require_supabase() -> Client:
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase is not configured")
    return client


def unwrap_response(response: Any) -> Any:
    if hasattr(response, "data"):
        return response.data
    return response

