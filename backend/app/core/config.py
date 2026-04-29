from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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
    ai_transcription_provider: str = "openai"
    ai_voice_draft_daily_limit: int = 50
    ai_voice_max_duration_seconds: int = 60
    ai_voice_notes_bucket: str = "voice-notes"

    anthropic_api_key: str | None = None
    merchant_chat_provider: Literal["anthropic", "mock", "stub"] = "mock"
    merchant_chat_model: str = "claude-sonnet-4-6"
    ai_merchant_chat_daily_limit: int = 50
    merchant_chat_log_salt: str = "dev-salt"
    whatsapp_provider: str = "mock"
    whatsapp_access_token: str | None = None
    whatsapp_from_number: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_webhook_secret: str | None = None
    whatsapp_verify_token: str | None = None

    payment_provider: str = "mock"
    tap_secret_key: str | None = None
    tap_webhook_secret: str | None = None
    tap_fee_percent: float = 2.75
    payment_redirect_base_url: str = "http://localhost:5173"

    database_url: str | None = None
    app_database_url: str | None = None
    system_database_url: str | None = None
    rls_mode: Literal["off", "shadow", "enforce"] = "off"
    repository_type: str = "postgres"

    frontend_dist: Path | None = None
    seed_demo_data: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def validate_rls_database_urls(self) -> "Settings":
        if self.repository_type != "postgres" or self.rls_mode == "off":
            return self
        if not self.app_database_url:
            raise ValueError("APP_DATABASE_URL is required when RLS_MODE is shadow or enforce")
        if not self.system_database_url:
            raise ValueError("SYSTEM_DATABASE_URL is required when RLS_MODE is shadow or enforce")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
