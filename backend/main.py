"""TenderClaw FastAPI application — entry point.
"""Backend launcher and glue for Wave 1.

This module is intentionally lightweight. It provides a minimal entry point
that can be invoked to start simple components or to wire in more complex
startup logic as Wave 1 matures.
"""

from __future__ import annotations

def start():
    # Placeholder for startup sequence; actual server startup is handled by the API layer
    print("TenderClaw backend startup (Wave 1 placeholder)")

Serves:
  - REST API at /api/*
  - WebSocket at /api/ws/{session_id}
  - React frontend at /tenderclaw
  - Runs on port 6669
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.api.channels import router as channels_router
from backend.config import settings
from backend.plugins.base import plugin_loader
from backend.services.session_store import session_store
from backend.tools.registry import tool_registry
from backend.tools.startup import register_builtin_tools
from backend.utils.logging import setup_logging

logger = logging.getLogger("tenderclaw")

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle."""
    setup_logging(settings.log_level)
    register_builtin_tools(tool_registry)
    
    # Initialize plugins
    _init_plugins()
    
    # Initialize channels (Telegram, Discord, etc.)
    _init_channels()
    
    logger.info(
        "TenderClaw started — http://%s:%d/tenderclaw",
        settings.host,
        settings.port,
    )
    yield
    await session_store.close_all()
    await _shutdown_channels()
    logger.info("TenderClaw stopped")


def _init_plugins() -> None:
    """Initialize plugin system."""
    from backend.agents.registry import agent_registry
    from backend.plugins.superpowers import SuperpowersPlugin
    
    # Load built-in plugins
    try:
        plugin_loader.load_plugin(SuperpowersPlugin())
        plugin_loader.register_all(tool_registry, agent_registry)
        logger.info("Loaded %d plugins", len(plugin_loader._plugins))
    except FileNotFoundError:
        logger.warning("Superpowers plugin not found, skipping")


def _init_channels() -> None:
    """Initialize channel integrations (Telegram, Discord)."""
    from backend.api import channels
    
    if settings.telegram_bot_token:
        channels.telegram_manager.start()
        logger.info("Telegram channel initialized")
    
    if settings.discord_token:
        channels.discord_manager.start()
        logger.info("Discord channel initialized")


async def _shutdown_channels() -> None:
    """Shutdown all channel integrations."""
    from backend.api import channels
    
    await channels.telegram_manager.stop()
    await channels.discord_manager.stop()


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="TenderClaw",
        version="0.1.0",
        description="Multi-agent, multi-model AI coding assistant",
        lifespan=lifespan,
    )

    # CORS for dev mode (Vite dev server on :5173)
    if settings.dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Mount API routes
    app.include_router(api_router, prefix="/api")

    # Serve React frontend build at /tenderclaw
    if FRONTEND_DIST.exists():
        app.mount(
            "/tenderclaw/assets",
            StaticFiles(directory=FRONTEND_DIST / "assets"),
            name="frontend-assets",
        )

        @app.get("/tenderclaw")
        @app.get("/tenderclaw/{path:path}")
        async def serve_frontend(path: str = "") -> FileResponse:
            """Serve the React SPA — all routes go to index.html."""
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()


def run() -> None:
    """CLI entry point — `tenderclaw` command."""
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.dev,
    )


if __name__ == "__main__":
    run()
