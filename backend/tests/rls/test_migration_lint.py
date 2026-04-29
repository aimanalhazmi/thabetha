from pathlib import Path

import pytest


def test_new_user_data_tables_have_rls_and_policy() -> None:
    migrations_dir = Path(__file__).resolve().parents[3] / "supabase/migrations"
    post_013 = sorted(path for path in migrations_dir.glob("0*.sql") if path.name > "013_rls_enforcement.sql")
    if not post_013:
        pytest.skip("no post-013 user-data migrations yet")

    for path in post_013:
        sql = path.read_text().lower()
        created_tables = [line.split("public.", 1)[1].split()[0].strip('";(') for line in sql.splitlines() if "create table" in line and "public." in line]
        for table in created_tables:
            assert f"alter table public.{table} enable row level security" in sql
            assert "policy" in sql and f"public.{table}" in sql
