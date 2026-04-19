"""Analytics API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/analytics", tags=["analytics"])


class EventRequest(BaseModel):
    event_name: str
    properties: dict[str, Any] | None = None


@router.post("/event")
async def log_event(request: EventRequest, session_id: str | None = None) -> dict[str, str]:
    """Log a custom event."""
    from backend.services.analytics import event_logger

    event_logger.log(
        event_name=request.event_name,
        properties=request.properties,
        session_id=session_id,
    )
    return {"status": "logged"}


@router.get("/events")
async def get_events(
    date: str | None = None,
    event_name: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get logged events."""
    from backend.services.analytics import event_logger

    events = event_logger.get_events(date, event_name, limit)
    return [e.to_dict() for e in events]


@router.get("/flags")
async def get_flags() -> dict[str, bool]:
    """Get all feature flags."""
    from backend.services.analytics import feature_flags

    return {name: flag.enabled for name, flag in feature_flags._flags.items()}


@router.get("/flags/{flag_name}")
async def get_flag(flag_name: str) -> dict[str, Any]:
    """Get specific feature flag."""
    from backend.services.analytics import feature_flags

    flag = feature_flags._flags.get(flag_name)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    return {"name": flag.name, "enabled": flag.enabled, "value": flag.value}


@router.post("/flags/{flag_name}")
async def set_flag(flag_name: str, enabled: bool, value: Any = None) -> dict[str, str]:
    """Set feature flag."""
    from backend.services.analytics import feature_flags

    feature_flags.set(flag_name, enabled, value)
    return {"status": "updated"}
