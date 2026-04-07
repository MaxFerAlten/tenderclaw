"""TenderClaw MCP package."""

from backend.mcp.client import (
    BuiltinMCPs,
    MCPError,
    MCPManager,
    McpClient,
    McpManager,
    mcp_manager,
)
from backend.mcp.lifecycle import (
    InvalidTransitionError,
    LifecycleEvent,
    LifecycleManager,
    ServerConfig,
    ServerLifecycle,
    ServerState,
    lifecycle_manager,
)

__all__ = [
    "BuiltinMCPs",
    "InvalidTransitionError",
    "LifecycleEvent",
    "LifecycleManager",
    "MCPError",
    "MCPManager",
    "McpClient",
    "McpManager",
    "ServerConfig",
    "ServerLifecycle",
    "ServerState",
    "lifecycle_manager",
    "mcp_manager",
]
