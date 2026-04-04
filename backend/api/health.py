"""Health check endpoint — GET /api/health."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

router = APIRouter()

_START_TIME: float = time.monotonic()
_VERSION: str = "0.1.0"


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return service status, version, and uptime in seconds."""
    uptime_seconds = round(time.monotonic() - _START_TIME, 2)
    return {
        "status": "ok",
        "version": _VERSION,
        "uptime_seconds": uptime_seconds,
    }
