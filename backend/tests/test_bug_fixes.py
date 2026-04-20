"""Tests for bug fixes - verify no regressions.

Tests cover:
- BridgeState StrEnum usage
- Unused imports cleanup
- WS task cleanup
"""

from __future__ import annotations

import pytest

from backend.bridge.remote_bridge import BridgeState


class TestBridgeState:
    """Test BridgeState enum behavior."""

    def test_bridgestate_is_string(self):
        """BridgeState values should be strings."""
        assert isinstance(BridgeState.DISCONNECTED, str)
        assert isinstance(BridgeState.CONNECTING, str)
        assert isinstance(BridgeState.CONNECTED, str)
        assert isinstance(BridgeState.AUTHENTICATED, str)

    def test_bridgestate_string_comparison(self):
        """BridgeState should support string comparison."""
        assert BridgeState.CONNECTED == "connected"
        assert BridgeState.DISCONNECTED != "connected"
        assert BridgeState.AUTHENTICATED == "authenticated"

    def test_bridgestate_value(self):
        """BridgeState values should match expected strings."""
        assert BridgeState.DISCONNECTED.value == "disconnected"
        assert BridgeState.CONNECTING.value == "connecting"
        assert BridgeState.CONNECTED.value == "connected"
        assert BridgeState.AUTHENTICATED.value == "authenticated"

    def test_bridgestate_from_string(self):
        """BridgeState should be constructable from string."""
        assert BridgeState("connected") == BridgeState.CONNECTED

    def test_bridgestate_enum_members(self):
        """BridgeState should have all expected members."""
        expected = {"DISCONNECTED", "CONNECTING", "CONNECTED", "AUTHENTICATED"}
        actual = {member.name for member in BridgeState}
        assert actual == expected


class TestHandlerImports:
    """Test that handler module imports work correctly."""

    def test_handler_can_be_imported(self):
        """AgentHandler should be importable without errors."""
        from backend.agents.handler import AgentHandler

        assert AgentHandler is not None

    def test_handler_execute_signature(self):
        """AgentHandler.execute_agent_turn should have correct signature."""
        from backend.agents.handler import AgentHandler
        import inspect

        sig = inspect.signature(AgentHandler.execute_agent_turn)
        params = list(sig.parameters.keys())
        assert "agent_name" in params
        assert "messages" in params


class TestRegistryImports:
    """Test that registry module imports work correctly."""

    def test_registry_can_be_imported(self):
        """AgentRegistry should be importable without errors."""
        from backend.agents.registry import AgentRegistry

        assert AgentRegistry is not None

    def test_registry_has_register_method(self):
        """AgentRegistry should have register method."""
        from backend.agents.registry import AgentRegistry

        assert hasattr(AgentRegistry, "register")
        assert hasattr(AgentRegistry, "get")
        assert hasattr(AgentRegistry, "list_agents")