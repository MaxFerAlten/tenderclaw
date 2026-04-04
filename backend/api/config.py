"""Config API — manage provider API keys and settings.

Keys are stored per-session in SessionData.api_keys, not in a global dict.
The global _session_config is kept only as a fallback for keyless sessions
(e.g. the OpenAI gateway which has no session context).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("tenderclaw.api.config")
router = APIRouter()


class ConfigUpdate(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    xai_api_key: str | None = None
    deepseek_api_key: str | None = None
    ollama_base_url: str | None = None
    lmstudio_base_url: str | None = None
    default_model: str | None = None
    # Optional: target a specific session
    session_id: str | None = None


class ConfigResponse(BaseModel):
    anthropic_configured: bool = False
    openai_configured: bool = False
    google_configured: bool = False
    xai_configured: bool = False
    deepseek_configured: bool = False
    ollama_base_url: str = ""
    lmstudio_base_url: str = ""
    default_model: str = ""


# Fallback global config (used when no session_id is provided)
_global_config: dict[str, Any] = {
    "anthropic_api_key": "",
    "openai_api_key": "",
    "google_api_key": "",
    "xai_api_key": "",
    "deepseek_api_key": "",
    "ollama_base_url": "",
    "lmstudio_base_url": "",
}

_PROVIDER_KEY_MAP = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "google": "google_api_key",
    "xai": "xai_api_key",
    "deepseek": "deepseek_api_key",
}


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    from backend.config import settings
    return ConfigResponse(
        anthropic_configured=bool(settings.anthropic_api_key or _global_config.get("anthropic_api_key")),
        openai_configured=bool(settings.openai_api_key or _global_config.get("openai_api_key")),
        google_configured=bool(settings.google_api_key or _global_config.get("google_api_key")),
        xai_configured=bool(settings.xai_api_key or _global_config.get("xai_api_key")),
        deepseek_configured=bool(settings.deepseek_api_key or _global_config.get("deepseek_api_key")),
        ollama_base_url=_global_config.get("ollama_base_url") or settings.ollama_base_url,
        lmstudio_base_url=_global_config.get("lmstudio_base_url") or settings.lmstudio_base_url,
        default_model=settings.default_model,
    )


@router.post("/config")
async def update_config(config: ConfigUpdate) -> dict[str, str]:
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    updates = config.model_dump(exclude_none=True, exclude={"session_id"})

    if config.session_id:
        # Store keys in the specific session — isolated, no leakage
        try:
            session = session_store.get(config.session_id)
            for field, value in updates.items():
                provider = next((p for p, k in _PROVIDER_KEY_MAP.items() if k == field), None)
                if provider:
                    session.set_api_key(provider, value)
                elif field == "ollama_base_url":
                    session.model_config["ollama_url"] = value
                elif field == "lmstudio_base_url":
                    session.model_config["lmstudio_url"] = value
            logger.info("Session %s config updated: %s", config.session_id, list(updates.keys()))
        except SessionNotFoundError:
            return {"status": "error", "message": f"Session not found: {config.session_id}"}
    else:
        # Update global fallback config
        for field, value in updates.items():
            if field in _global_config:
                _global_config[field] = value
        logger.info("Global config updated: %s", list(updates.keys()))

    return {"status": "ok", "message": "Configuration updated"}


def get_session_api_key(provider: str, session_id: str | None = None) -> str | None:
    """Get API key for a provider, checking session first, then global, then env."""
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    # 1. Session-specific key
    if session_id:
        try:
            session = session_store.get(session_id)
            key = session.get_api_key(provider)
            if key:
                return key
        except SessionNotFoundError:
            pass

    # 2. Global fallback config
    key_field = _PROVIDER_KEY_MAP.get(provider)
    if key_field and _global_config.get(key_field):
        return _global_config[key_field]

    # 3. Environment / .env
    env_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
        "xai": settings.xai_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    return env_map.get(provider) or None


def get_session_ollama_url(session_id: str | None = None) -> str:
    """Get Ollama base URL, checking session config first."""
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    if session_id:
        try:
            session = session_store.get(session_id)
            url = session.model_config.get("ollama_url")
            if url:
                return url
        except SessionNotFoundError:
            pass

    return _global_config.get("ollama_base_url") or settings.ollama_base_url


def get_session_lmstudio_url(session_id: str | None = None) -> str:
    """Get LM Studio base URL, checking session config first."""
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    if session_id:
        try:
            session = session_store.get(session_id)
            url = session.model_config.get("lmstudio_url")
            if url:
                return url
        except SessionNotFoundError:
            pass

    return _global_config.get("lmstudio_base_url") or settings.lmstudio_base_url
