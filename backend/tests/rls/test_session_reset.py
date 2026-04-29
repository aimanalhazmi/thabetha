from app.core.config import Settings


def test_rls_enforcement_requires_dedicated_urls() -> None:
    try:
        Settings(repository_type="postgres", rls_mode="enforce", app_database_url=None, system_database_url=None)
    except ValueError as exc:
        assert "APP_DATABASE_URL" in str(exc)
    else:
        raise AssertionError("enforce mode must reject missing RLS database URLs")
