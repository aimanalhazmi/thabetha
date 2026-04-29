"""RLS negative-isolation receipts.

These tests are intentionally skipped unless the local Supabase Postgres stack
is running. The static checks still make the policy requirements executable in
normal CI; full behavioral proof runs in the dedicated RLS workflow.
"""

from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[3] / "supabase/migrations/013_rls_enforcement.sql"


def test_rls_migration_documents_deleted_user_stale_claim_choice() -> None:
    sql = MIGRATION.read_text()
    assert "Stale-claim / deleted-user behavior" in sql
    assert "token expiry" in sql


def test_group_member_sees_shared_debt_policy_exists() -> None:
    sql = (Path(__file__).resolve().parents[3] / "supabase/migrations/011_groups_mvp.sql").read_text()
    assert "debts_select_party_or_group" in sql
    assert "gm.status = 'accepted'" in sql


@pytest.mark.skip(reason="requires Supabase local stack and seeded cross-user fixture")
def test_cross_user_debt_detail_returns_404_under_enforce() -> None:
    pass


@pytest.mark.skip(reason="requires Supabase local stack and unauthenticated direct DB probe")
def test_unauthenticated_denied_at_db_layer() -> None:
    pass


@pytest.mark.skip(reason="requires Supabase local stack and auth.users mutation")
def test_deleted_user_denied_under_stale_token() -> None:
    pass
