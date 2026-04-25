from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.domain import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    return HealthOut(status="ok", service=settings.app_name, environment=settings.app_env)

