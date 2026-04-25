"""Apply application schema migrations at startup."""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "supabase" / "migrations"


def apply_migrations(database_url: str) -> None:
    """Run pending SQL migration files against Postgres.

    Idempotent: tracks applied files in a ``schema_migrations`` table.
    """
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()

        for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            row = conn.execute(
                "SELECT 1 FROM public.schema_migrations WHERE filename = %s",
                (sql_file.name,),
            ).fetchone()
            if row:
                logger.info("Migration %s already applied, skipping", sql_file.name)
                continue

            logger.info("Applying migration %s ...", sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO public.schema_migrations (filename) VALUES (%s)",
                (sql_file.name,),
            )
            conn.commit()
            logger.info("Migration %s applied successfully", sql_file.name)
