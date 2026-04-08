"""Diagnostics endpoints for runtime health checks (e.g. Ollama)."""

from __future__ import annotations

import logging
from typing import Dict

import httpx
from fastapi import APIRouter

logger = logging.getLogger("tenderclaw.api.diagnostics")
router = APIRouter()


@router.get("/ollama", tags=["diagnostics"])
async def ollama_health() -> Dict[str, str]:
    """Test connectivity to the local Ollama instance."""
    base = "http://localhost:11434/v1"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=2.0) as client:
            resp = await client.get("/models")
            ok = resp.status_code == 200
            detail = resp.text[:300] if resp.text else ""
        return {"status": "ok" if ok else "not_ok", "detail": detail}
    except Exception as exc:
        logger.error("Ollama diagnostics error: %s", exc)
        return {"status": "error", "detail": str(exc)}


@router.get("/lmstudio/models", tags=["diagnostics"])
async def lmstudio_models(base_url: str | None = None) -> list[str]:
    """Return list of model IDs loaded in LM Studio."""
    from backend.config import settings

    base = base_url or settings.lmstudio_base_url
    if not base.endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=3.0) as client:
            resp = await client.get("/models")
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception as exc:
        logger.error("LM Studio models fetch error: %s", exc)
        return []


@router.get("/lmstudio", tags=["diagnostics"])
async def lmstudio_health(base_url: str | None = None) -> Dict[str, str]:
    """Test connectivity to LM Studio.

    Optionally pass ?base_url=http://host:port to test a custom address.
    """
    from backend.config import settings

    base = base_url or settings.lmstudio_base_url
    if not base.endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=3.0) as client:
            resp = await client.get("/models")
            ok = resp.status_code == 200
            models: list[str] = []
            if ok:
                try:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                except Exception as exc:
                    logger.debug("Failed to parse LM Studio models response: %s", exc)
            detail = resp.text[:300] if not ok else ""
        return {
            "status": "ok" if ok else "not_ok",
            "base_url": base,
            "models": ", ".join(models) if models else "(none loaded)",
            "detail": detail,
        }
    except Exception as exc:
        logger.error("LM Studio diagnostics error: %s", exc)
        return {"status": "error", "base_url": base, "detail": str(exc)}


@router.get("/openrouter/models", tags=["diagnostics"])
async def openrouter_models() -> list[str]:
    """Return list of models available via OpenRouter."""
    from backend.config import settings
    from backend.api.config import _global_config

    key = settings.openrouter_api_key or _global_config.get("openrouter_api_key", "")
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception as exc:
        logger.error("OpenRouter models fetch error: %s", exc)
        return []


@router.get("/opencode/models", tags=["diagnostics"])
async def opencode_models() -> list[str]:
    """Return list of models available via OpenCode."""
    from backend.config import settings
    from backend.api.config import _global_config

    key = settings.opencode_api_key or _global_config.get("opencode_api_key", "")
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://opencode.ai/zen/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            # API returns IDs like "opencode/model-name" — strip the namespace prefix
            # so the model name stored in sessions matches what the API expects
            return [
                m["id"].removeprefix("opencode/")
                for m in data.get("data", [])
                if m.get("id")
            ]
    except Exception as exc:
        logger.error("OpenCode models fetch error: %s", exc)
        return []
