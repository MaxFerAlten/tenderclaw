"""SDK API — Agent SDK endpoints for external integrations.

Provides programmatic access to TenderClaw agents, tools, and sessions
for external clients and plugins.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.agents.registry import agent_registry
from backend.services.session_store import session_store
from shared.sdk_errors import SessionNotFoundError
from shared.sdk_types import (
    AgentManifest,
    SDKExecuteResponse,
    SDKSchema,
    StreamEvent,
    StreamEventType,
    ToolDefinition,
)

if TYPE_CHECKING:
    from backend.schemas.tools import ToolSpec

logger = logging.getLogger("tenderclaw.api.sdk")
router = APIRouter()


def _agent_to_manifest(agent_dict: dict[str, Any]) -> AgentManifest:
    """Convert agent dict to AgentManifest."""
    return AgentManifest(
        name=agent_dict["name"],
        description=agent_dict.get("description", ""),
        mode=agent_dict.get("mode", "subagent"),
        default_model=agent_dict.get("default_model", "claude-sonnet-4-20250514"),
        category=agent_dict.get("category", "utility"),
        cost=agent_dict.get("cost", "cheap"),
        system_prompt=agent_dict.get("system_prompt", ""),
        max_tokens=agent_dict.get("max_tokens", 16384),
        tools=agent_dict.get("tools", []),
        enabled=agent_dict.get("enabled", True),
        is_builtin=agent_dict.get("is_builtin", False),
    )


def _tool_to_definition(tool_spec: ToolSpec) -> ToolDefinition:
    """Convert ToolSpec to ToolDefinition."""
    return ToolDefinition(
        name=tool_spec.name,
        description=tool_spec.description,
        input_schema=tool_spec.input_schema,
        risk_level=tool_spec.risk_level.value,
        is_read_only=tool_spec.is_read_only,
    )


class ExecuteRequest(BaseModel):
    """SDK execute request body."""

    command: str
    agent_name: str | None = None
    session_id: str | None = None
    message: str | None = None
    config: dict[str, Any] | None = None


@router.get("/agents", response_model=list[AgentManifest])
async def list_agents() -> list[AgentManifest]:
    """Return all available agents for SDK consumption."""
    agents = agent_registry.list_all()
    return [_agent_to_manifest(a.model_dump()) for a in agents]


@router.get("/agents/{name}", response_model=AgentManifest)
async def get_agent(name: str) -> AgentManifest:
    """Return a specific agent manifest."""
    try:
        agent = agent_registry.get(name)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from err
    return _agent_to_manifest(agent.model_dump())


@router.get("/tools", response_model=list[ToolDefinition])
async def list_tools() -> list[ToolDefinition]:
    """Return all available tools for SDK consumption."""
    from backend.tools.registry import tool_registry

    tools = tool_registry.list_tools()
    return [_tool_to_definition(t) for t in tools]


@router.post("/execute", response_model=SDKExecuteResponse)
async def execute_sdk_command(request: ExecuteRequest) -> SDKExecuteResponse:
    """Execute an SDK command."""
    if request.command == "create_session":
        session = session_store.create()
        return SDKExecuteResponse(
            success=True,
            session_id=session.session_id,
            message=f"Session created: {session.session_id}",
        )

    elif request.command == "send_message":
        if not request.session_id:
            return SDKExecuteResponse(success=False, error="session_id required")
        if not request.message:
            return SDKExecuteResponse(success=False, error="message required")

        try:
            session = session_store.get(request.session_id)
        except SessionNotFoundError:
            return SDKExecuteResponse(success=False, error=f"Session not found: {request.session_id}")

        session.model = request.config.get("model") if request.config else session.model

        return SDKExecuteResponse(
            success=True,
            session_id=request.session_id,
            message="Message queued",
        )

    elif request.command == "list_agents":
        agents = agent_registry.list_all()
        return SDKExecuteResponse(
            success=True,
            message=f"Found {len(agents)} agents",
        )

    else:
        return SDKExecuteResponse(
            success=False,
            error=f"Unknown command: {request.command}",
        )


@router.get("/schema", response_model=SDKSchema)
async def get_sdk_schema() -> SDKSchema:
    """Return the complete SDK schema for client generation."""
    from backend.tools.registry import tool_registry

    agents = agent_registry.list_all()
    tools = tool_registry.list_tools()

    return SDKSchema(
        version="1.0.0",
        agents=[_agent_to_manifest(a.model_dump()) for a in agents],
        tools=[_tool_to_definition(t) for t in tools],
    )


@router.websocket("/stream/{session_id}")
async def sdk_stream(ws: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for SDK streaming events."""
    await ws.accept()

    try:
        session_store.get(session_id)
    except SessionNotFoundError:
        await ws.send_json(
            StreamEvent(
                type=StreamEventType.ERROR,
                session_id=session_id,
                data={"error": f"Session not found: {session_id}"},
            ).model_dump()
        )
        await ws.close(code=4004, reason="session_not_found")
        return

    logger.info("SDK stream connected: %s", session_id)

    async def send_event(event: StreamEvent) -> None:
        await ws.send_json(event.model_dump())

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == "send_message":
                message = raw.get("message", "")
                if message:
                    await send_event(
                        StreamEvent(
                            type=StreamEventType.DELTA,
                            session_id=session_id,
                            data={"text": f"Received: {message}"},
                        )
                    )

            elif msg_type == "ping":
                await ws.send_json({"type": "pong", "session_id": session_id})

            else:
                await send_event(
                    StreamEvent(
                        type=StreamEventType.ERROR,
                        session_id=session_id,
                        data={"error": f"Unknown message type: {msg_type}"},
                    )
                )
    except WebSocketDisconnect:
        logger.info("SDK stream disconnected: %s", session_id)
    except Exception as exc:
        logger.error("SDK stream error for %s: %s", session_id, exc)
        try:
            await ws.send_json(
                StreamEvent(
                    type=StreamEventType.ERROR,
                    session_id=session_id,
                    data={"error": str(exc)},
                ).model_dump()
            )
        except Exception:
            logger.debug("Failed to send SDK stream error (connection likely closed)")
