"""Config API — manage provider API keys and settings.

Keys are stored per-session in SessionData.api_keys, not in a global dict.
The global _session_config is kept only as a fallback for keyless sessions
(e.g. the OpenAI gateway which has no session context).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("tenderclaw.api.config")
router = APIRouter()

_GLOBAL_CONFIG_PATH = Path(".tenderclaw") / "global_config.json"


class ConfigUpdate(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    xai_api_key: str | None = None
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    opencode_api_key: str | None = None
    ollama_base_url: str | None = None
    lmstudio_base_url: str | None = None
    llamacpp_base_url: str | None = None
    gpt4free_base_url: str | None = None
    default_model: str | None = None
    selected_provider: str | None = None  # explicit provider override
    session_id: str | None = None


class ConfigResponse(BaseModel):
    anthropic_configured: bool = False
    openai_configured: bool = False
    google_configured: bool = False
    xai_configured: bool = False
    deepseek_configured: bool = False
    openrouter_configured: bool = False
    opencode_configured: bool = False
    ollama_base_url: str = ""
    lmstudio_base_url: str = ""
    llamacpp_base_url: str = ""
    gpt4free_base_url: str = ""
    default_model: str = ""
    selected_provider: str = ""


# Fallback global config (used when no session_id is provided)
_global_config: dict[str, Any] = {
    "anthropic_api_key": "",
    "openai_api_key": "",
    "google_api_key": "",
    "xai_api_key": "",
    "deepseek_api_key": "",
    "openrouter_api_key": "",
    "opencode_api_key": "",
    "ollama_base_url": "",
    "lmstudio_base_url": "",
    "llamacpp_base_url": "",
    "gpt4free_base_url": "",
    "selected_provider": "",
}


def _load_global_config() -> None:
    """Load persisted global config from disk into _global_config."""
    if not _GLOBAL_CONFIG_PATH.exists():
        return
    try:
        data = json.loads(_GLOBAL_CONFIG_PATH.read_text(encoding="utf-8"))
        for key in _global_config:
            if key in data and data[key]:
                _global_config[key] = data[key]
    except Exception as exc:
        logger.warning("Failed to load global config from disk: %s", exc)


def _save_global_config() -> None:
    """Persist _global_config to disk."""
    try:
        _GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GLOBAL_CONFIG_PATH.write_text(json.dumps(_global_config, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save global config to disk: %s", exc)


# Load on module import
_load_global_config()

_PROVIDER_KEY_MAP = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "google": "google_api_key",
    "xai": "xai_api_key",
    "deepseek": "deepseek_api_key",
    "openrouter": "openrouter_api_key",
    "opencode": "opencode_api_key",
}


@router.get("/config", response_model=ConfigResponse)
async def get_config(session_id: str | None = None) -> ConfigResponse:
    """Return current config.

    ``session_id`` (optional query param): when provided, per-session values
    (e.g. ``selected_provider``, local base URLs stored in ``model_config``)
    take precedence over the global fallback. This lets the frontend rehydrate
    the Settings screen with the user's actual active provider after a reload.
    """
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    session_cfg: dict[str, str] = {}
    session_keys: dict[str, str] = {}
    if session_id:
        try:
            session = session_store.get(session_id)
            session_cfg = dict(session.model_config or {})
            session_keys = dict(session.api_keys or {})
        except SessionNotFoundError:
            pass

    def _pick(session_key: str, global_key: str, settings_attr: str = "") -> str:
        val = session_cfg.get(session_key)
        if val:
            return val
        val = _global_config.get(global_key)
        if val:
            return val
        return getattr(settings, settings_attr, "") if settings_attr else ""

    def _configured(provider: str, settings_attr: str) -> bool:
        return bool(
            session_keys.get(provider)
            or _global_config.get(f"{provider}_api_key")
            or getattr(settings, settings_attr, "")
        )

    return ConfigResponse(
        anthropic_configured=_configured("anthropic", "anthropic_api_key"),
        openai_configured=_configured("openai", "openai_api_key"),
        google_configured=_configured("google", "google_api_key"),
        xai_configured=_configured("xai", "xai_api_key"),
        deepseek_configured=_configured("deepseek", "deepseek_api_key"),
        openrouter_configured=_configured("openrouter", "openrouter_api_key"),
        opencode_configured=_configured("opencode", "opencode_api_key"),
        ollama_base_url=_pick("ollama_url", "ollama_base_url", "ollama_base_url"),
        lmstudio_base_url=_pick("lmstudio_url", "lmstudio_base_url", "lmstudio_base_url"),
        llamacpp_base_url=_pick("llamacpp_url", "llamacpp_base_url", "llamacpp_base_url"),
        gpt4free_base_url=_pick("gpt4free_url", "gpt4free_base_url", "gpt4free_base_url"),
        default_model=settings.default_model,
        selected_provider=(
            session_cfg.get("selected_provider")
            or _global_config.get("selected_provider")
            or ""
        ),
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
                    session.model_config[field] = value
                elif field == "ollama_base_url":
                    session.model_config["ollama_url"] = value
                elif field == "lmstudio_base_url":
                    session.model_config["lmstudio_url"] = value
                elif field == "llamacpp_base_url":
                    session.model_config["llamacpp_url"] = value
                elif field == "gpt4free_base_url":
                    session.model_config["gpt4free_url"] = value
                elif field == "selected_provider":
                    session.model_config["selected_provider"] = value
            logger.info("Session %s config updated: %s", config.session_id, list(updates.keys()))
        except SessionNotFoundError:
            pass

    # ALWAYS update global config as fallback
    for field, value in updates.items():
        if field in _global_config:
            _global_config[field] = value
    logger.info("Global config updated: %s", list(updates.keys()))
    _save_global_config()

    return {"status": "ok", "message": "Configuration updated"}


@router.get("/config/status")
async def get_config_status() -> dict[str, dict[str, object]]:
    """Return per-provider configuration status (key set + validated)."""
    from backend.config import settings

    providers = {
        "anthropic": settings.anthropic_api_key or _global_config.get("anthropic_api_key", ""),
        "openai": settings.openai_api_key or _global_config.get("openai_api_key", ""),
        "google": settings.google_api_key or _global_config.get("google_api_key", ""),
        "xai": settings.xai_api_key or _global_config.get("xai_api_key", ""),
        "deepseek": settings.deepseek_api_key or _global_config.get("deepseek_api_key", ""),
        "openrouter": settings.openrouter_api_key or _global_config.get("openrouter_api_key", ""),
        "opencode": settings.opencode_api_key or _global_config.get("opencode_api_key", ""),
    }
    # Validation results are stored per-request in _validated_providers
    return {
        provider: {
            "configured": bool(key),
            "validated": _validated_providers.get(provider, False),
            "error": _validation_errors.get(provider, ""),
        }
        for provider, key in providers.items()
    }


@router.patch("/config/validate/{provider}")
async def validate_provider(provider: str) -> dict[str, object]:
    """Make a cheap probe call to validate a provider's API key."""
    key = get_session_api_key(provider)
    if not key:
        return {"ok": False, "error": "No API key configured"}

    try:
        ok, error = await _probe_provider(provider, key)
        _validated_providers[provider] = ok
        _validation_errors[provider] = error if not ok else ""
        return {"ok": ok, "error": error}
    except Exception as exc:
        _validation_errors[provider] = str(exc)
        return {"ok": False, "error": str(exc)}


async def _probe_provider(provider: str, key: str) -> tuple[bool, str]:
    """Make a minimal API call to check if the key is valid."""
    import httpx

    headers = {"Content-Type": "application/json"}
    try:
        if provider == "anthropic":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "openai":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "google":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "xai":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.x.ai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "deepseek":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "openrouter":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        elif provider == "opencode":
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://opencode.ai/zen/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, ""
                return False, f"HTTP {r.status_code}"

        return False, f"Unknown provider: {provider}"

    except httpx.TimeoutException:
        return False, "Timeout — provider unreachable"
    except Exception as exc:
        return False, str(exc)


# In-memory validation cache (reset on server restart)
_validated_providers: dict[str, bool] = {}
_validation_errors: dict[str, str] = {}


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
        "openrouter": settings.openrouter_api_key,
        "opencode": settings.opencode_api_key,
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


def get_session_llamacpp_url(session_id: str | None = None) -> str:
    """Get llama.cpp base URL, checking session config first."""
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    if session_id:
        try:
            session = session_store.get(session_id)
            url = session.model_config.get("llamacpp_url")
            if url:
                return url
        except SessionNotFoundError:
            pass

    return _global_config.get("llamacpp_base_url") or settings.llamacpp_base_url


def get_session_gpt4free_url(session_id: str | None = None) -> str:
    """Get gpt4free base URL, checking session config first."""
    from backend.config import settings
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    if session_id:
        try:
            session = session_store.get(session_id)
            url = session.model_config.get("gpt4free_url")
            if url:
                return url
        except SessionNotFoundError:
            pass

    return _global_config.get("gpt4free_base_url") or settings.gpt4free_base_url
