"""Repository implementations."""

from __future__ import annotations

from app.repositories.base import Repository

_repo: Repository | None = None


def get_repository() -> Repository:
    """Return the singleton repository instance based on configuration."""
    global _repo
    if _repo is not None:
        return _repo

    from app.core.config import get_settings

    settings = get_settings()

    if settings.repository_type == "postgres":
        from psycopg_pool import ConnectionPool

        from app.repositories.postgres import PostgresRepository

        pool = ConnectionPool(settings.database_url, min_size=2, max_size=10)
        _repo = PostgresRepository(pool)
    else:
        from app.repositories.memory import InMemoryRepository

        _repo = InMemoryRepository()

    return _repo


__all__ = ["Repository", "get_repository"]
