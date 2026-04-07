"""Notifications API — REST endpoints for notification management.

GET  /api/notifications           — list active notifications
GET  /api/notifications/all       — list all (including dismissed)
POST /api/notifications/dismiss   — dismiss single notification
POST /api/notifications/dismiss-all — dismiss all notifications
GET  /api/notifications/stats     — notification stats
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.notifications import notification_service

router = APIRouter(prefix="/notifications")


@router.get("")
async def list_notifications(session_id: str | None = None, limit: int = 50):
    items = notification_service.list_active(session_id=session_id, limit=limit)
    return {"notifications": [n.model_dump(mode="json") for n in items]}


@router.get("/all")
async def list_all_notifications(limit: int = 100):
    items = notification_service.list_all(limit=limit)
    return {"notifications": [n.model_dump(mode="json") for n in items]}


@router.post("/dismiss")
async def dismiss_notification(notification_id: str):
    ok = notification_service.dismiss(notification_id)
    return {"dismissed": ok}


@router.post("/dismiss-all")
async def dismiss_all(session_id: str | None = None):
    count = notification_service.dismiss_all(session_id=session_id)
    return {"dismissed_count": count}


@router.get("/stats")
async def notification_stats():
    return notification_service.stats()
