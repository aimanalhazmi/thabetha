from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Thabetha"
    app_env: str = "local"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"])

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_storage_bucket: str = "receipts"
    receipt_signed_url_ttl_seconds: int = 3600
    receipt_archive_retention_months: int = 6

    openai_api_key: str | None = None
    whatsapp_provider: str = "mock"
    whatsapp_access_token: str | None = None
    whatsapp_from_number: str | None = None

    database_url: str | None = None
    repository_type: str = "postgres"

    frontend_dist: Path | None = None
    seed_demo_data: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
