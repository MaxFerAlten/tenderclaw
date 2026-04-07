"""MCP Client — interface for Model Context Protocol.

Allows TenderClaw to use external tools provided by MCP servers
(stdio, SSE, etc.). Bridges MCP tools into TenderClaw's tool registry.
Integrates with the lifecycle state machine for server management.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.mcp.lifecycle import (
    InvalidTransitionError,
    LifecycleManager,
    ServerConfig,
    ServerState,
    lifecycle_manager,
)

logger = logging.getLogger("tenderclaw.mcp")

_request_counter = 0


def _next_id() -> int:
    global _request_counter
    _request_counter += 1
    return _request_counter


class MCPError(Exception):
    """Error communicating with an MCP server."""


class McpClient:
    """MCP client for stdio-based servers with full tool discovery."""

    def __init__(self, server_command: list[str], name: str = "") -> None:
        self.server_command = server_command
        self.name = name or server_command[0]
        self.process: asyncio.subprocess.Process | None = None
        self._tools: list[dict[str, Any]] = []

    async def connect(self) -> list[dict[str, Any]]:
        """Spawn the MCP server process, initialize, and return tools."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("Connected to MCP server: %s", self.name)

        # Initialize per MCP spec
        resp = await self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TenderClaw", "version": "0.1.0"},
        })
        logger.info("MCP server initialized: %s", resp.get("result", {}).get("serverInfo", {}))

        # Send initialized notification
        await self._notify("notifications/initialized", {})

        # Discover tools
        return await self.list_tools()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover available tools from the MCP server."""
        resp = await self._rpc("tools/list", {})
        self._tools = resp.get("result", {}).get("tools", [])
        logger.info("MCP server %s provides %d tools", self.name, len(self._tools))
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server."""
        resp = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = resp.get("result", {})
        if resp.get("error"):
            raise MCPError(resp["error"].get("message", "MCP tool error"))
        return result

    async def disconnect(self) -> None:
        """Kill the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
            logger.info("Disconnected MCP server: %s", self.name)

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and read the response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise MCPError(f"MCP server {self.name} not connected")

        request = {"jsonrpc": "2.0", "method": method, "params": params, "id": _next_id()}
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()

        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
        if not line:
            raise MCPError(f"MCP server {self.name} closed stdout")
        return json.loads(line.decode())

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write((json.dumps(notification) + "\n").encode())
        await self.process.stdin.drain()


class McpManager:
    """Manages multiple MCP server connections with lifecycle integration."""

    def __init__(self, lm: LifecycleManager | None = None) -> None:
        self._clients: dict[str, McpClient] = {}
        self._lifecycle = lm or lifecycle_manager

    def register(self, config: ServerConfig) -> None:
        """Register a server config for lifecycle management."""
        self._lifecycle.register(config)

    async def add_server(self, name: str, command: list[str], **kwargs: Any) -> McpClient:
        """Register, connect, and activate an MCP server."""
        config = ServerConfig(name=name, command=command, **kwargs)

        # Register in lifecycle if not already
        if self._lifecycle.get(name) is None:
            self._lifecycle.register(config)

        client = McpClient(command, name=name)
        self._clients[name] = client

        async def _connect() -> list[dict[str, Any]]:
            return await client.connect()

        await self._lifecycle.activate(name, _connect)
        return client

    async def activate(self, name: str) -> McpClient:
        """Activate a previously registered (or paused/terminated) server."""
        server = self._lifecycle.get(name)
        if server is None:
            raise MCPError(f"Server {name} not registered")

        client = self._clients.get(name)
        if client is None:
            client = McpClient(server.config.command, name=name)
            self._clients[name] = client

        async def _connect() -> list[dict[str, Any]]:
            return await client.connect()

        await self._lifecycle.activate(name, _connect)
        return client

    async def pause(self, name: str) -> None:
        """Pause a server (disconnect but keep config)."""
        client = self._clients.get(name)

        async def _disc() -> None:
            if client:
                await client.disconnect()

        await self._lifecycle.pause(name, _disc)

    async def terminate(self, name: str) -> None:
        """Terminate a server and clean up."""
        client = self._clients.pop(name, None)

        async def _disc() -> None:
            if client:
                await client.disconnect()

        await self._lifecycle.terminate(name, _disc)

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all tools from all active servers, prefixed with server name."""
        all_tools: list[dict[str, Any]] = []
        for server in self._lifecycle.list_active():
            client = self._clients.get(server.name)
            tools = client._tools if client else server.tools
            for tool in tools:
                all_tools.append({
                    **tool,
                    "name": f"mcp_{server.name}_{tool['name']}",
                    "_server": server.name,
                    "_original_name": tool["name"],
                })
        return all_tools

    async def call_tool(self, server_or_prefixed: str, tool_name: str | None = None, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a tool on an MCP server.

        Supports two calling conventions:
        - call_tool("server_name", "tool_name", {args})  — used by builtin services
        - call_tool("mcp_server_tool", arguments={args})  — used by bridge (prefixed name)
        """
        if tool_name is not None:
            # Direct server + tool name
            client = self._clients.get(server_or_prefixed)
            if client is None:
                raise MCPError(f"No MCP client for server: {server_or_prefixed}")
            server = self._lifecycle.get(server_or_prefixed)
            if server and not server.is_active:
                raise MCPError(f"Server {server_or_prefixed} is {server.state.value}, not active")
            return await client.call_tool(tool_name, arguments or {})

        # Prefixed name lookup
        for server_name, client in self._clients.items():
            prefix = f"mcp_{server_name}_"
            if server_or_prefixed.startswith(prefix):
                original = server_or_prefixed[len(prefix):]
                return await client.call_tool(original, arguments or {})
        raise MCPError(f"No MCP server found for tool: {server_or_prefixed}")

    async def disconnect_all(self) -> None:
        """Terminate all servers and disconnect."""
        async def _disc(name: str) -> None:
            client = self._clients.pop(name, None)
            if client:
                await client.disconnect()

        await self._lifecycle.terminate_all(_disc)

    def get_server_info(self, name: str) -> dict[str, Any] | None:
        """Get lifecycle info for a server."""
        server = self._lifecycle.get(name)
        return server.to_info() if server else None

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered servers with their lifecycle state."""
        return [s.to_info() for s in self._lifecycle.list_all()]

    @property
    def server_count(self) -> int:
        return len(self._lifecycle.list_all())

    @property
    def active_count(self) -> int:
        return len(self._lifecycle.list_active())


class BuiltinMCPs:
    """Factory for built-in MCP server configurations."""

    @staticmethod
    def context7() -> ServerConfig:
        return ServerConfig(
            name="context7",
            command=["npx", "-y", "@upstash/context7-mcp@latest"],
            auto_activate=True,
            timeout=60.0,
        )

    @staticmethod
    def grep_app() -> ServerConfig:
        return ServerConfig(
            name="grep_app",
            command=["npx", "-y", "@anthropics/grep-app-mcp@latest"],
            auto_activate=True,
        )

    @staticmethod
    def websearch(provider: str = "exa", api_key: str | None = None) -> ServerConfig:
        env: dict[str, str] = {}
        if api_key:
            env["EXA_API_KEY"] = api_key
        return ServerConfig(
            name="websearch",
            command=["npx", "-y", f"@anthropics/{provider}-mcp@latest"],
            env=env,
            auto_activate=True,
        )


# Aliases for backward compatibility
MCPManager = McpManager

# Module-level instance
mcp_manager = McpManager()
