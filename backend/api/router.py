"""Top-level API router — aggregates all sub-routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.health import router as health_router
from backend.api.sessions import router as sessions_router
from backend.api.tools_api import router as tools_router
from backend.api.ws import router as ws_router
from backend.api.gateway import router as gateway_router
from backend.api.channels import router as channels_router
from backend.api.diagnostics import router as diagnostics_router
from backend.api.mvp import router as mvp_router
from backend.api.config import router as config_router
from backend.api.agents_api import router as agents_router
from backend.api.skills_api import router as skills_router
from backend.api.history_api import router as history_router
from backend.api.sdk_api import router as sdk_router
from backend.api.cost_api import router as cost_router
from backend.api.migrations_api import router as migrations_router
from backend.api.keybindings_api import router as keybindings_router
from backend.api.coordinator_api import router as coordinator_router
from backend.api.bridge_api import router as bridge_router
from backend.api.analytics_api import router as analytics_router
from backend.api.ralph_api import router as ralph_router
from backend.api.keywords_api import router as keywords_router
from backend.api.modes_api import router as modes_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])
api_router.include_router(ws_router, tags=["websocket"])
api_router.include_router(gateway_router, prefix="/v1", tags=["openai-compat"])
api_router.include_router(channels_router, tags=["channels"])
api_router.include_router(diagnostics_router, prefix="/diagnostics", tags=["diagnostics"])
api_router.include_router(config_router, tags=["config"])
api_router.include_router(mvp_router, prefix="/mvp", tags=["mvp"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(skills_router, prefix="/skills", tags=["skills"])
api_router.include_router(history_router, prefix="/history", tags=["history"])
api_router.include_router(sdk_router, prefix="/sdk", tags=["sdk"])
api_router.include_router(cost_router, tags=["costs"])
api_router.include_router(migrations_router, tags=["migrations"])
api_router.include_router(keybindings_router, prefix="/keybindings", tags=["keybindings"])
api_router.include_router(coordinator_router, tags=["coordinator"])
api_router.include_router(bridge_router, prefix="/bridge", tags=["bridge"])
api_router.include_router(analytics_router, tags=["analytics"])
api_router.include_router(ralph_router, tags=["ralph"])
api_router.include_router(keywords_router, tags=["keywords"])
api_router.include_router(modes_router, tags=["mode"])
