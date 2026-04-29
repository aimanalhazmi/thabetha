from pathlib import Path


def test_profiles_preview_policy_exists() -> None:
    sql = (Path(__file__).resolve().parents[3] / "supabase/migrations/013_rls_enforcement.sql").read_text()
    assert "Profiles preview for authenticated" in sql
    assert "auth.role() = 'authenticated'" in sql
