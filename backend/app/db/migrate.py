"""Migration module — with Supabase local, migrations are managed via `supabase db reset`.

This module is kept for backward-compat but skips if Supabase already applied them.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def apply_migrations(database_url: str) -> None:
    """No-op when using Supabase managed migrations.

    Supabase CLI handles schema via `supabase/migrations/*.sql`.
    """
    logger.info("Skipping app-level migrations — Supabase CLI manages the schema.")
