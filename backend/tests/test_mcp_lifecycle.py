"""Tests for MCP lifecycle state machine and client integration."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.mcp.lifecycle import (
    InvalidTransitionError,
    LifecycleEvent,
    LifecycleManager,
    ServerConfig,
    ServerLifecycle,
    ServerState,
)
from backend.mcp.client import (
    BuiltinMCPs,
    MCPError,
    McpManager,
)


# --- ServerConfig ---


def test_server_config_defaults():
    cfg = ServerConfig(name="test", command=["echo"])
    assert cfg.auto_activate is True
    assert cfg.timeout == 30.0
    assert cfg.restart_on_error is False
    assert cfg.max_restarts == 3


# --- ServerLifecycle ---


def test_initial_state():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    assert lc.state == ServerState.CREATED
    assert lc.name == "s1"
    assert lc.is_active is False
    assert lc.tools == []


def test_valid_transitions():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    assert lc.state == ServerState.ACTIVATING
    lc.mark_active(tools=[{"name": "t1"}])
    assert lc.state == ServerState.ACTIVE
    assert lc.is_active is True
    assert len(lc.tools) == 1
    lc.mark_paused()
    assert lc.state == ServerState.PAUSED
    assert lc.is_active is False
    assert lc.is_available is True


def test_active_to_terminate():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    lc.mark_active()
    lc.mark_terminating()
    assert lc.state == ServerState.TERMINATING
    lc.mark_terminated()
    assert lc.state == ServerState.TERMINATED
    assert lc.tools == []


def test_invalid_transition_raises():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    with pytest.raises(InvalidTransitionError, match="Cannot transition"):
        lc.mark_active()  # Can't go CREATED -> ACTIVE directly


def test_error_state():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    lc.mark_error("connection refused")
    assert lc.state == ServerState.ERROR
    assert lc.error_message == "connection refused"


def test_restart_from_error():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"], restart_on_error=True))
    lc.mark_activating()
    lc.mark_error("timeout")
    # Can retry from error
    lc.mark_activating()
    lc.mark_active()
    assert lc.state == ServerState.ACTIVE


def test_restart_from_terminated():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    lc.mark_active()
    lc.mark_terminating()
    lc.mark_terminated()
    # Can restart from terminated
    lc.mark_activating()
    lc.mark_active()
    assert lc.state == ServerState.ACTIVE


def test_can_restart():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"], restart_on_error=True, max_restarts=2))
    assert lc.can_restart() is True
    lc.record_restart()
    assert lc.can_restart() is True
    lc.record_restart()
    assert lc.can_restart() is False


def test_events_recorded():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    lc.mark_active()
    assert len(lc.events) == 2
    assert lc.events[0].from_state == ServerState.CREATED
    assert lc.events[0].to_state == ServerState.ACTIVATING
    assert lc.events[1].to_state == ServerState.ACTIVE


def test_to_info():
    lc = ServerLifecycle(ServerConfig(name="s1", command=["echo", "hello"]))
    lc.mark_activating()
    lc.mark_active(tools=[{"name": "a"}, {"name": "b"}])
    info = lc.to_info()
    assert info["name"] == "s1"
    assert info["state"] == "active"
    assert info["tool_count"] == 2
    assert info["command"] == ["echo", "hello"]


# --- LifecycleManager ---


def test_register():
    mgr = LifecycleManager()
    cfg = ServerConfig(name="s1", command=["echo"])
    lc = mgr.register(cfg)
    assert lc.state == ServerState.CREATED
    assert mgr.get("s1") is lc


def test_register_duplicate_active_raises():
    mgr = LifecycleManager()
    cfg = ServerConfig(name="s1", command=["echo"])
    lc = mgr.register(cfg)
    lc.mark_activating()
    lc.mark_active()
    with pytest.raises(ValueError, match="already registered"):
        mgr.register(cfg)


def test_register_duplicate_terminated_ok():
    mgr = LifecycleManager()
    cfg = ServerConfig(name="s1", command=["echo"])
    lc = mgr.register(cfg)
    lc.mark_activating()
    lc.mark_active()
    lc.mark_terminating()
    lc.mark_terminated()
    # Re-register after terminated is OK
    lc2 = mgr.register(cfg)
    assert lc2.state == ServerState.CREATED


def test_list_all_and_active():
    mgr = LifecycleManager()
    lc1 = mgr.register(ServerConfig(name="s1", command=["echo"]))
    lc2 = mgr.register(ServerConfig(name="s2", command=["echo"]))
    lc1.mark_activating()
    lc1.mark_active()
    assert len(mgr.list_all()) == 2
    assert len(mgr.list_active()) == 1


def test_remove():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))
    assert mgr.remove("s1") is True
    assert mgr.get("s1") is None


def test_remove_active_fails():
    mgr = LifecycleManager()
    lc = mgr.register(ServerConfig(name="s1", command=["echo"]))
    lc.mark_activating()
    lc.mark_active()
    assert mgr.remove("s1") is False


@pytest.mark.asyncio
async def test_activate():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))

    mock_tools = [{"name": "tool1"}, {"name": "tool2"}]

    async def connect() -> list[dict[str, Any]]:
        return mock_tools

    server = await mgr.activate("s1", connect)
    assert server.state == ServerState.ACTIVE
    assert len(server.tools) == 2


@pytest.mark.asyncio
async def test_activate_error():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))

    async def connect() -> list[dict[str, Any]]:
        raise ConnectionError("refused")

    with pytest.raises(ConnectionError):
        await mgr.activate("s1", connect)

    assert mgr.get("s1").state == ServerState.ERROR


@pytest.mark.asyncio
async def test_activate_auto_restart():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"], restart_on_error=True, max_restarts=2))

    call_count = 0

    async def connect() -> list[dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("retry")
        return [{"name": "ok"}]

    server = await mgr.activate("s1", connect)
    assert server.state == ServerState.ACTIVE
    assert server.restart_count == 2
    assert call_count == 3


@pytest.mark.asyncio
async def test_pause():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))

    async def connect() -> list[dict[str, Any]]:
        return []

    await mgr.activate("s1", connect)
    disc = AsyncMock()
    server = await mgr.pause("s1", disc)
    assert server.state == ServerState.PAUSED
    disc.assert_awaited_once()


@pytest.mark.asyncio
async def test_terminate():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))

    async def connect() -> list[dict[str, Any]]:
        return [{"name": "t"}]

    await mgr.activate("s1", connect)
    disc = AsyncMock()
    server = await mgr.terminate("s1", disc)
    assert server.state == ServerState.TERMINATED
    assert server.tools == []
    disc.assert_awaited_once()


@pytest.mark.asyncio
async def test_terminate_all():
    mgr = LifecycleManager()
    for name in ("s1", "s2", "s3"):
        mgr.register(ServerConfig(name=name, command=["echo"]))

    async def connect() -> list[dict[str, Any]]:
        return []

    await mgr.activate("s1", connect)
    await mgr.activate("s2", connect)
    # s3 stays CREATED

    disc = AsyncMock()
    await mgr.terminate_all(disc)
    assert mgr.get("s1").state == ServerState.TERMINATED
    assert mgr.get("s2").state == ServerState.TERMINATED
    assert mgr.get("s3").state == ServerState.CREATED  # unchanged


@pytest.mark.asyncio
async def test_lifecycle_hooks():
    mgr = LifecycleManager()
    mgr.register(ServerConfig(name="s1", command=["echo"]))

    events: list[LifecycleEvent] = []

    async def hook(event: LifecycleEvent) -> None:
        events.append(event)

    mgr.add_hook(hook)

    async def connect() -> list[dict[str, Any]]:
        return []

    await mgr.activate("s1", connect)
    assert len(events) == 2  # activating + active
    assert events[0].to_state == ServerState.ACTIVATING
    assert events[1].to_state == ServerState.ACTIVE


def test_get_stats():
    mgr = LifecycleManager()
    lc1 = mgr.register(ServerConfig(name="s1", command=["echo"]))
    lc1.mark_activating()
    lc1.mark_active(tools=[{"name": "a"}])
    mgr.register(ServerConfig(name="s2", command=["echo"]))

    stats = mgr.get_stats()
    assert stats["total"] == 2
    assert stats["active"] == 1
    assert stats["total_tools"] == 1
    assert stats["by_state"]["active"] == 1
    assert stats["by_state"]["created"] == 1


# --- BuiltinMCPs ---


def test_builtin_context7():
    cfg = BuiltinMCPs.context7()
    assert cfg.name == "context7"
    assert "npx" in cfg.command[0]


def test_builtin_grep_app():
    cfg = BuiltinMCPs.grep_app()
    assert cfg.name == "grep_app"


def test_builtin_websearch():
    cfg = BuiltinMCPs.websearch(api_key="test-key")
    assert cfg.name == "websearch"
    assert cfg.env["EXA_API_KEY"] == "test-key"


def test_builtin_websearch_no_key():
    cfg = BuiltinMCPs.websearch()
    assert "EXA_API_KEY" not in cfg.env


# --- McpManager integration ---


def test_manager_register():
    mgr = McpManager(lm=LifecycleManager())
    cfg = ServerConfig(name="s1", command=["echo"])
    mgr.register(cfg)
    assert mgr.server_count == 1


def test_manager_list_servers():
    lm = LifecycleManager()
    mgr = McpManager(lm=lm)
    mgr.register(ServerConfig(name="s1", command=["echo"]))
    mgr.register(ServerConfig(name="s2", command=["echo"]))
    servers = mgr.list_servers()
    assert len(servers) == 2
    assert servers[0]["state"] == "created"
