"""Tests for GET /config hydration — B2.

Verifies that `selected_provider` and local base URLs stored in a session's
`model_config` are returned by the config endpoint, so the frontend can
rehydrate the Settings screen on reload.
"""

from __future__ import annotations

import uuid

import pytest

from backend.api import config as config_module
from backend.api.config import ConfigUpdate, get_config, update_config
from backend.services.session_store import SessionData, session_store


@pytest.fixture
def session():
    sid = f"test_{uuid.uuid4().hex[:10]}"
    data = SessionData(session_id=sid, model="claude-3-5-sonnet")
    session_store._sessions[sid] = data
    try:
        yield data
    finally:
        session_store._sessions.pop(sid, None)


@pytest.fixture(autouse=True)
def clean_global_config():
    snapshot = dict(config_module._global_config)
    try:
        for k in list(config_module._global_config.keys()):
            config_module._global_config[k] = ""
        yield
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(snapshot)


class TestGetConfigHydration:
    async def test_no_session_returns_empty_selected_provider(self):
        resp = await get_config()
        assert resp.selected_provider == ""

    async def test_global_selected_provider_exposed(self):
        config_module._global_config["selected_provider"] = "gpt4free"
        resp = await get_config()
        assert resp.selected_provider == "gpt4free"

    async def test_session_selected_provider_wins_over_global(self, session):
        config_module._global_config["selected_provider"] = "ollama"
        session.model_config["selected_provider"] = "gpt4free"
        resp = await get_config(session_id=session.session_id)
        assert resp.selected_provider == "gpt4free"

    async def test_session_model_round_trips(self, session):
        session.model = "big-pickle"
        resp = await get_config(session_id=session.session_id)
        assert resp.model == "big-pickle"

    async def test_global_model_exposed_without_session(self):
        config_module._global_config["model"] = "big-pickle"
        resp = await get_config()
        assert resp.model == "big-pickle"

    async def test_session_local_urls_round_trip(self, session):
        session.model_config["gpt4free_url"] = "http://session-host:1337"
        session.model_config["ollama_url"] = "http://session-host:11434"
        resp = await get_config(session_id=session.session_id)
        assert resp.gpt4free_base_url == "http://session-host:1337"
        assert resp.ollama_base_url == "http://session-host:11434"

    async def test_global_urls_used_when_session_missing(self, session):
        config_module._global_config["gpt4free_base_url"] = "http://global-host:1337"
        # session has no gpt4free_url → global fallback
        resp = await get_config(session_id=session.session_id)
        assert resp.gpt4free_base_url == "http://global-host:1337"

    async def test_unknown_session_id_falls_back_to_global(self):
        config_module._global_config["selected_provider"] = "lmstudio"
        resp = await get_config(session_id="does-not-exist")
        assert resp.selected_provider == "lmstudio"

    async def test_session_api_keys_flag_configured_true(self, session):
        session.set_api_key("anthropic", "sk-test-key")
        resp = await get_config(session_id=session.session_id)
        assert resp.anthropic_configured is True

    async def test_all_keyless_provider_values_round_trip(self, session):
        for provider in ("gpt4free", "ollama", "lmstudio", "llamacpp"):
            session.model_config["selected_provider"] = provider
            resp = await get_config(session_id=session.session_id)
            assert resp.selected_provider == provider, (
                f"selected_provider={provider!r} did not round-trip: got {resp.selected_provider!r}"
            )

    async def test_update_config_persists_session_model_without_websocket(self, session):
        session.model = "claude-sonnet-4-20250514"

        await update_config(
            ConfigUpdate(
                session_id=session.session_id,
                model="big-pickle",
                selected_provider="opencode",
            )
        )

        assert session.model == "big-pickle"
        assert session.model_config["selected_provider"] == "opencode"

    async def test_update_config_with_missing_session_still_updates_global_fallback(self):
        await update_config(
            ConfigUpdate(
                session_id="missing-session",
                model="big-pickle",
                selected_provider="opencode",
            )
        )

        assert config_module._global_config["model"] == "big-pickle"
        assert config_module._global_config["selected_provider"] == "opencode"
