"""MCP Server Lifecycle — state machine for MCP server management.

Manages the full lifecycle of MCP servers: Create → Activate → Pause/Resume → Terminate.
Each server has a well-defined state and only valid transitions are allowed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger("tenderclaw.mcp.lifecycle")


class ServerState(str, Enum):
    """MCP server lifecycle states."""

    CREATED = "created"
    ACTIVATING = "activating"
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    ERROR = "error"


# Valid state transitions
_TRANSITIONS: dict[ServerState, set[ServerState]] = {
    ServerState.CREATED: {ServerState.ACTIVATING, ServerState.TERMINATED},
    ServerState.ACTIVATING: {ServerState.ACTIVE, ServerState.ERROR},
    ServerState.ACTIVE: {ServerState.PAUSED, ServerState.TERMINATING, ServerState.ERROR},
    ServerState.PAUSED: {ServerState.ACTIVATING, ServerState.TERMINATING, ServerState.TERMINATED},
    ServerState.TERMINATING: {ServerState.TERMINATED, ServerState.ERROR},
    ServerState.TERMINATED: {ServerState.ACTIVATING},  # allow restart
    ServerState.ERROR: {ServerState.ACTIVATING, ServerState.TERMINATED},  # allow retry or cleanup
}


class ServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str
    command: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    auto_activate: bool = True
    timeout: float = 30.0
    restart_on_error: bool = False
    max_restarts: int = 3


class LifecycleEvent(BaseModel):
    """A recorded lifecycle event."""

    server_name: str
    from_state: ServerState
    to_state: ServerState
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: str = ""


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""


class ServerLifecycle:
    """Manages the lifecycle state machine for a single MCP server."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.state = ServerState.CREATED
        self.created_at = datetime.now()
        self.activated_at: datetime | None = None
        self.error_message: str | None = None
        self.restart_count: int = 0
        self.events: list[LifecycleEvent] = []
        self.tools: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_active(self) -> bool:
        return self.state == ServerState.ACTIVE

    @property
    def is_available(self) -> bool:
        return self.state in (ServerState.ACTIVE, ServerState.PAUSED)

    def _transition(self, to_state: ServerState, reason: str = "") -> None:
        """Perform a state transition with validation."""
        allowed = _TRANSITIONS.get(self.state, set())
        if to_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition {self.name} from {self.state.value} to {to_state.value}. "
                f"Allowed: {', '.join(s.value for s in allowed)}"
            )
        event = LifecycleEvent(
            server_name=self.name,
            from_state=self.state,
            to_state=to_state,
            reason=reason,
        )
        self.events.append(event)
        logger.info(
            "MCP %s: %s -> %s%s",
            self.name,
            self.state.value,
            to_state.value,
            f" ({reason})" if reason else "",
        )
        self.state = to_state

    def mark_activating(self) -> None:
        self._transition(ServerState.ACTIVATING, "connecting")

    def mark_active(self, tools: list[dict[str, Any]] | None = None) -> None:
        self._transition(ServerState.ACTIVE, f"ready, {len(tools or [])} tools")
        self.activated_at = datetime.now()
        self.error_message = None
        if tools is not None:
            self.tools = tools

    def mark_paused(self, reason: str = "user request") -> None:
        self._transition(ServerState.PAUSED, reason)

    def mark_terminating(self) -> None:
        self._transition(ServerState.TERMINATING, "shutting down")

    def mark_terminated(self) -> None:
        self._transition(ServerState.TERMINATED, "stopped")
        self.tools = []

    def mark_error(self, error: str) -> None:
        self._transition(ServerState.ERROR, error)
        self.error_message = error

    def can_restart(self) -> bool:
        if not self.config.restart_on_error:
            return False
        return self.restart_count < self.config.max_restarts

    def record_restart(self) -> None:
        self.restart_count += 1

    def to_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "command": self.config.command,
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "tool_count": len(self.tools),
            "restart_count": self.restart_count,
            "error": self.error_message,
        }


LifecycleHook = Callable[[LifecycleEvent], Awaitable[None]]


class LifecycleManager:
    """Manages lifecycle of all MCP servers with hooks support."""

    def __init__(self) -> None:
        self._servers: dict[str, ServerLifecycle] = {}
        self._hooks: list[LifecycleHook] = []

    def register(self, config: ServerConfig) -> ServerLifecycle:
        """Register a new server (state: CREATED)."""
        if config.name in self._servers:
            existing = self._servers[config.name]
            if existing.state not in (ServerState.TERMINATED, ServerState.ERROR):
                raise ValueError(
                    f"Server {config.name} already registered in state {existing.state.value}"
                )
        lifecycle = ServerLifecycle(config)
        self._servers[config.name] = lifecycle
        logger.info("MCP server registered: %s", config.name)
        return lifecycle

    def get(self, name: str) -> ServerLifecycle | None:
        return self._servers.get(name)

    def list_all(self) -> list[ServerLifecycle]:
        return list(self._servers.values())

    def list_active(self) -> list[ServerLifecycle]:
        return [s for s in self._servers.values() if s.is_active]

    def remove(self, name: str) -> bool:
        server = self._servers.get(name)
        if server and server.state in (ServerState.TERMINATED, ServerState.ERROR, ServerState.CREATED):
            del self._servers[name]
            return True
        return False

    def add_hook(self, hook: LifecycleHook) -> None:
        self._hooks.append(hook)

    async def _fire_hooks(self, event: LifecycleEvent) -> None:
        for hook in self._hooks:
            try:
                await hook(event)
            except Exception as exc:
                logger.warning("Lifecycle hook error: %s", exc)

    async def activate(self, name: str, connect_fn: Callable[[], Awaitable[list[dict[str, Any]]]]) -> ServerLifecycle:
        """Activate a server: CREATED/PAUSED/TERMINATED/ERROR → ACTIVE.

        connect_fn should connect to the server and return its tool list.
        """
        server = self._servers.get(name)
        if server is None:
            raise ValueError(f"Unknown server: {name}")

        server.mark_activating()
        await self._fire_hooks(server.events[-1])

        try:
            tools = await asyncio.wait_for(connect_fn(), timeout=server.config.timeout)
            server.mark_active(tools)
            await self._fire_hooks(server.events[-1])
            return server
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            server.mark_error(error_msg)
            await self._fire_hooks(server.events[-1])

            if server.can_restart():
                server.record_restart()
                logger.info("Auto-restarting %s (attempt %d)", name, server.restart_count)
                return await self.activate(name, connect_fn)

            raise

    async def pause(self, name: str, disconnect_fn: Callable[[], Awaitable[None]] | None = None) -> ServerLifecycle:
        """Pause a server: ACTIVE → PAUSED."""
        server = self._servers.get(name)
        if server is None:
            raise ValueError(f"Unknown server: {name}")

        server.mark_paused()
        await self._fire_hooks(server.events[-1])

        if disconnect_fn:
            try:
                await disconnect_fn()
            except Exception as exc:
                logger.warning("Error during pause disconnect for %s: %s", name, exc)

        return server

    async def terminate(self, name: str, disconnect_fn: Callable[[], Awaitable[None]] | None = None) -> ServerLifecycle:
        """Terminate a server: ACTIVE/PAUSED → TERMINATED."""
        server = self._servers.get(name)
        if server is None:
            raise ValueError(f"Unknown server: {name}")

        server.mark_terminating()
        await self._fire_hooks(server.events[-1])

        if disconnect_fn:
            try:
                await disconnect_fn()
            except Exception as exc:
                logger.warning("Error during terminate disconnect for %s: %s", name, exc)

        server.mark_terminated()
        await self._fire_hooks(server.events[-1])
        return server

    async def terminate_all(self, disconnect_fn: Callable[[str], Awaitable[None]] | None = None) -> None:
        """Terminate all active/paused servers."""
        for name, server in list(self._servers.items()):
            if server.state in (ServerState.ACTIVE, ServerState.PAUSED):
                try:
                    async def _disc() -> None:
                        if disconnect_fn:
                            await disconnect_fn(name)
                    await self.terminate(name, _disc)
                except Exception as exc:
                    logger.error("Error terminating %s: %s", name, exc)

    def get_stats(self) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        for server in self._servers.values():
            by_state[server.state.value] = by_state.get(server.state.value, 0) + 1
        return {
            "total": len(self._servers),
            "by_state": by_state,
            "active": len(self.list_active()),
            "total_tools": sum(len(s.tools) for s in self.list_active()),
        }


# Module-level instance
lifecycle_manager = LifecycleManager()
