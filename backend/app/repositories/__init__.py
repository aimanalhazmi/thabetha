"""Repository implementations."""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from app.repositories.base import Repository

_repo: Repository | None = None
app_pool: ConnectionPool | None = None
system_pool: ConnectionPool | None = None


def get_repository() -> Repository:
    """Return the singleton repository instance based on configuration."""
    global _repo
    if _repo is not None:
        return _repo

    from app.core.config import get_settings

    settings = get_settings()

    if settings.repository_type == "postgres":
        from app.repositories.postgres import PostgresRepository

        if settings.rls_mode == "off" and not settings.app_database_url:
            pool = ConnectionPool(settings.database_url, min_size=2, max_size=10)
            _repo = PostgresRepository(pool)
        else:
            global app_pool, system_pool
            app_pool = ConnectionPool(settings.app_database_url, min_size=2, max_size=10)
            system_pool = ConnectionPool(settings.system_database_url, min_size=1, max_size=5)
            _repo = PostgresRepository(system_pool if settings.rls_mode == "shadow" else app_pool)
    else:
        from app.repositories.memory import InMemoryRepository

        _repo = InMemoryRepository()

    return _repo


__all__ = ["Repository", "app_pool", "get_repository", "system_pool"]
