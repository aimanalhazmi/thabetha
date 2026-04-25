from fastapi import APIRouter

from app.api import ai, dashboards, debts, groups, health, notifications, profiles, qr

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(qr.router, prefix="/qr", tags=["qr"])
api_router.include_router(debts.router, prefix="/debts", tags=["debts"])
api_router.include_router(dashboards.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])

