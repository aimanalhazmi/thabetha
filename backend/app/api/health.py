from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.domain import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    supabase_connected = False

    if settings.repository_type == "postgres" and settings.database_url:
        try:
            import psycopg

            with psycopg.connect(settings.database_url) as conn:
                conn.execute("SELECT 1")
            supabase_connected = True
        except Exception:
            supabase_connected = False
    else:
        from app.db.supabase import get_supabase_client

        client = get_supabase_client()
        if client is not None:
            try:
                client.table("profiles").select("id", count="exact").limit(0).execute()
                supabase_connected = True
            except Exception:
                supabase_connected = False

    return HealthOut(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        supabase_connected=supabase_connected,
    )
