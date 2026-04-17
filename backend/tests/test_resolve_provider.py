"""Unit tests for `resolve_provider` — the centralized (model, config) → provider mapper.

This helper is the single source of truth used by conversation.py, ws.py, and
model_router.stream_message. The contract it encodes:

  config.selected_provider (if truthy) wins over detect_provider(model).
"""

from __future__ import annotations

import pytest

from backend.services import model_router
from backend.services.model_router import resolve_provider


# ---------------------------------------------------------------------------
# Helper: force detect_provider to a known value so we isolate resolve_provider
# ---------------------------------------------------------------------------


@pytest.fixture
def forced_detection(monkeypatch):
    """Patch detect_provider to return a deterministic sentinel value."""
    calls: list[str] = []

    async def _fake_detect(model: str) -> str:
        calls.append(model)
        return "FROM_DETECT"

    monkeypatch.setattr(model_router, "detect_provider", _fake_detect)
    return calls


# ---------------------------------------------------------------------------
# Selected-provider wins
# ---------------------------------------------------------------------------


class TestSelectedProviderWins:
    @pytest.mark.parametrize(
        "model",
        [
            "claude-3-5-sonnet",
            "gpt-4o",
            "gemini-2.0-flash",
            "grok-2",
            "whatever-random",
        ],
    )
    async def test_explicit_selection_overrides_model_name(self, forced_detection, model):
        cfg = {"selected_provider": "gpt4free"}
        result = await resolve_provider(model, cfg)
        assert result == "gpt4free"
        assert forced_detection == [], "detect_provider must not be called when selection is explicit"

    @pytest.mark.parametrize(
        "provider",
        ["gpt4free", "ollama", "lmstudio", "llamacpp", "anthropic", "openai"],
    )
    async def test_any_selected_provider_value_passes_through(
        self, forced_detection, provider
    ):
        cfg = {"selected_provider": provider}
        assert await resolve_provider("claude-3-5-sonnet", cfg) == provider


# ---------------------------------------------------------------------------
# Fallback to detect_provider
# ---------------------------------------------------------------------------


class TestFallsBackToDetect:
    async def test_no_config_falls_back(self, forced_detection):
        result = await resolve_provider("claude-3-5-sonnet", None)
        assert result == "FROM_DETECT"
        assert forced_detection == ["claude-3-5-sonnet"]

    async def test_empty_config_falls_back(self, forced_detection):
        result = await resolve_provider("claude-3-5-sonnet", {})
        assert result == "FROM_DETECT"
        assert forced_detection == ["claude-3-5-sonnet"]

    async def test_empty_string_selection_falls_back(self, forced_detection):
        # Frontend may send selected_provider="" when the field isn't filled.
        result = await resolve_provider("claude-3-5-sonnet", {"selected_provider": ""})
        assert result == "FROM_DETECT"
        assert forced_detection == ["claude-3-5-sonnet"]

    async def test_none_selection_falls_back(self, forced_detection):
        result = await resolve_provider("gpt-4o", {"selected_provider": None})
        assert result == "FROM_DETECT"


# ---------------------------------------------------------------------------
# Config with unrelated keys must not leak into resolution
# ---------------------------------------------------------------------------


class TestUnrelatedConfigKeys:
    async def test_other_config_keys_ignored(self, forced_detection):
        cfg = {
            "anthropic_api_key": "sk-leaked",
            "gpt4free_url": "http://localhost:1337",
            "permission_mode": "auto",
            # no selected_provider → must fall back
        }
        result = await resolve_provider("claude-3-5-sonnet", cfg)
        assert result == "FROM_DETECT"
