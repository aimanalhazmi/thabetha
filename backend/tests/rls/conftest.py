import os
from collections.abc import Callable

import pytest
from jose import jwt

os.environ["REPOSITORY_TYPE"] = "postgres"
os.environ.setdefault("RLS_MODE", "enforce")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres")
os.environ.setdefault("APP_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres")
os.environ.setdefault("SYSTEM_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres")
os.environ.setdefault("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-at-least-32-characters-long")


@pytest.fixture
def as_user() -> Callable[[str], dict[str, str]]:
    def _headers(uid: str) -> dict[str, str]:
        token = jwt.encode({"sub": uid, "role": "authenticated", "aud": "authenticated"}, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def rls_mode(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    def _set(value: str) -> None:
        monkeypatch.setenv("RLS_MODE", value)
        from app.core.config import get_settings

        get_settings.cache_clear()

    return _set
