from fastapi import APIRouter

from app.api import ai, auth, dashboards, debts, groups, health, notifications, profiles, qr, receipt_files, webhooks_whatsapp

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(qr.router, prefix="/qr", tags=["qr"])
api_router.include_router(debts.router, prefix="/debts", tags=["debts"])
api_router.include_router(receipt_files.router, tags=["receipt-files"])
api_router.include_router(dashboards.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(webhooks_whatsapp.router, tags=["webhooks"])
