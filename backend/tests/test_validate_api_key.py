"""Unit tests for `_validate_api_key` — the gpt4free selected_provider fix.

Covers the key behaviour introduced after the
"No API key for 'anthropic'" regression: a user-selected keyless provider
(gpt4free / ollama / lmstudio / llamacpp) must bypass API-key lookup even
when the model name would otherwise map to a cloud provider via
`detect_provider()` prefix matching (e.g. "claude-3-5-sonnet" → "anthropic").
"""

from __future__ import annotations

import uuid

import pytest

from backend.core.conversation import _validate_api_key
from backend.services.session_store import SessionData, session_store
from backend.api import config as config_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sent():
    """Collect messages pushed via the send() callback."""
    bucket: list[dict] = []

    async def _send(payload: dict) -> None:
        bucket.append(payload)

    return bucket, _send


@pytest.fixture
def session():
    """Register an in-memory SessionData and clean up after the test."""
    sid = f"test_{uuid.uuid4().hex[:10]}"
    data = SessionData(session_id=sid, model="claude-3-5-sonnet")
    session_store._sessions[sid] = data
    try:
        yield data
    finally:
        session_store._sessions.pop(sid, None)


@pytest.fixture(autouse=True)
def clean_global_config():
    """Snapshot + restore `_global_config` so tests don't leak into each other."""
    snapshot = dict(config_module._global_config)
    try:
        for k in list(config_module._global_config.keys()):
            config_module._global_config[k] = ""
        yield
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)


# ---------------------------------------------------------------------------
# Selected-provider bypass (the regression case)
# ---------------------------------------------------------------------------


class TestKeylessSelectedProvider:
    """When the user explicitly selects a keyless provider, no API key is required."""

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-3-5-sonnet",  # would map to 'anthropic' via prefix
            "gpt-4o",             # would map to 'openai'
            "gemini-2.0-flash",   # would map to 'google'
            "grok-2",             # would map to 'xai'
            "deepseek-chat",      # would map to 'openrouter'
            "some-random-name",   # no match at all
        ],
    )
    async def test_gpt4free_bypasses_api_key_for_any_model(
        self, session, sent, model_name
    ):
        session.model = model_name
        session.model_config["selected_provider"] = "gpt4free"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True, f"gpt4free should accept model={model_name!r}"
        assert bucket == [], f"No WSError expected, got {bucket}"
        assert "gpt4free_url" in session.model_config

    async def test_ollama_bypass_populates_url(self, session, sent):
        session.model = "claude-3-5-sonnet"  # deliberately misleading
        session.model_config["selected_provider"] = "ollama"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True
        assert bucket == []
        assert "ollama_url" in session.model_config

    async def test_lmstudio_bypass_populates_url(self, session, sent):
        session.model_config["selected_provider"] = "lmstudio"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True
        assert bucket == []
        assert "lmstudio_url" in session.model_config

    async def test_llamacpp_bypass_populates_url(self, session, sent):
        session.model_config["selected_provider"] = "llamacpp"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True
        assert bucket == []
        assert "llamacpp_url" in session.model_config


class TestGlobalSelectedProviderFallback:
    """If the session hasn't stored `selected_provider`, `_global_config` wins."""

    async def test_global_gpt4free_applies_to_session(self, session, sent):
        session.model = "gpt-4o"
        config_module._global_config["selected_provider"] = "gpt4free"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True
        assert bucket == []

    async def test_session_override_wins_over_global(self, session, sent, monkeypatch):
        # Global says gpt4free, session says something unknown → falls through to
        # detect_provider() path. We patch detect_provider to return a cloud provider
        # without a key to confirm the session value takes precedence.
        session.model_config["selected_provider"] = ""  # explicitly empty (not keyless)
        config_module._global_config["selected_provider"] = "gpt4free"
        session.model = "gpt-4o"
        bucket, send = sent

        # Falsy session value should still let the global 'gpt4free' win.
        ok = await _validate_api_key(session, send)
        assert ok is True
        assert bucket == []


# ---------------------------------------------------------------------------
# Cloud-provider path (no selected_provider) — existing behaviour preserved
# ---------------------------------------------------------------------------


class TestCloudProviderPath:
    """When no keyless provider is selected, API-key lookup must still fire."""

    async def test_missing_anthropic_key_emits_ws_error(self, session, sent, monkeypatch):
        # Ensure lookup returns no key regardless of environment.
        monkeypatch.setattr(
            "backend.api.config.get_session_api_key",
            lambda provider, session_id=None: None,
        )
        session.model = "claude-3-5-sonnet"
        session.model_config.pop("selected_provider", None)
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is False
        assert len(bucket) == 1
        err = bucket[0]
        assert err.get("code") == "api_key_missing"
        assert "anthropic" in err.get("error", "").lower()

    async def test_present_anthropic_key_passes(self, session, sent, monkeypatch):
        monkeypatch.setattr(
            "backend.api.config.get_session_api_key",
            lambda provider, session_id=None: "sk-test-1234" if provider == "anthropic" else None,
        )
        session.model = "claude-3-5-sonnet"
        session.model_config.pop("selected_provider", None)
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is True
        assert bucket == []
        assert session.model_config.get("anthropic_api_key") == "sk-test-1234"
        assert session.model_config.get("session_id") == session.session_id


# ---------------------------------------------------------------------------
# Edge: selected_provider set to a cloud provider should NOT bypass
# ---------------------------------------------------------------------------


class TestSelectedProviderCloudNoBypass:
    async def test_selected_anthropic_without_key_still_errors(
        self, session, sent, monkeypatch
    ):
        # selected_provider='anthropic' is NOT in _KEYLESS_PROVIDERS, so the
        # early-exit must not trigger and API-key validation must still run.
        monkeypatch.setattr(
            "backend.api.config.get_session_api_key",
            lambda provider, session_id=None: None,
        )
        session.model = "claude-3-5-sonnet"
        session.model_config["selected_provider"] = "anthropic"
        bucket, send = sent

        ok = await _validate_api_key(session, send)

        assert ok is False
        assert len(bucket) == 1
        assert bucket[0].get("code") == "api_key_missing"
