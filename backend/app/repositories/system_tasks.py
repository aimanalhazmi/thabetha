"""Allow-listed elevated database sessions for system-owned work.

Permitted callers:
- lazy commitment-score sweeper in repositories.postgres
- database-owned signup trigger path
- explicitly reviewed future cron-like jobs
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection


@contextmanager
def elevated_connection() -> Iterator[Connection]:
    from app.repositories import system_pool

    if system_pool is None:
        raise RuntimeError("system_pool is not configured")
    with system_pool.connection() as conn:
        try:
            yield conn
        finally:
            conn.execute("RESET ALL")
            conn.execute("RESET ROLE")
