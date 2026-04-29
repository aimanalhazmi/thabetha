from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.domain import HealthOut

router = APIRouter()


def _health_payload(settings: Settings) -> HealthOut:
    db_connected = False

    if settings.repository_type == "postgres" and settings.database_url:
        try:
            import psycopg

            with psycopg.connect(settings.database_url) as conn:
                conn.execute("SELECT 1")
            db_connected = True
        except Exception:
            db_connected = False

    return HealthOut(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        supabase_connected=db_connected,
        rls_mode=settings.rls_mode,
    )


@router.get("/health", response_model=HealthOut)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    return _health_payload(settings)


@router.get("/healthz", response_model=HealthOut)
def healthz(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    return _health_payload(settings)
