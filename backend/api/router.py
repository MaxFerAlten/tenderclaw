"""Top-level API router — aggregates all sub-routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.health import router as health_router
from backend.api.sessions import router as sessions_router
from backend.api.tools_api import router as tools_router
from backend.api.ws import router as ws_router
from backend.api.gateway import router as gateway_router
from backend.api.channels import router as channels_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])
api_router.include_router(ws_router, tags=["websocket"])
api_router.include_router(gateway_router, tags=["openai-compat"])
api_router.include_router(channels_router, tags=["channels"])
