"""Tool runner — executes tool uses from a conversation turn.

Handles permission gating (ASK → wait for WS response), tool execution,
and result collection. Kept separate from the main agentic loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from backend.hooks.dispatcher import hook_dispatcher
from backend.hooks.permissions import check_permission
from backend.schemas.hooks import HookPoint
from backend.schemas.messages import ToolResultBlock, ToolUseBlock
from backend.schemas.permissions import PermissionDecision, PermissionMode
from backend.schemas.tools import ToolInput, ToolResult
from backend.schemas.ws import WSPermissionRequest, WSToolResult
from backend.services.session_store import SessionData
from backend.tools.base import ToolContext
from backend.tools.execution import execute_tool
from backend.tools.registry import tool_registry

logger = logging.getLogger("tenderclaw.core.tool_runner")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]

PERMISSION_TIMEOUT_SECS = 120


async def run_tool_uses(
    tool_uses: list[ToolUseBlock],
    session: SessionData,
    message_id: str,
    send: SendFn,
) -> list[ToolResultBlock]:
    """Execute all tool uses for a turn, gating on permissions where needed."""
    results: list[ToolResultBlock] = []

    for tu in tool_uses:
        if session.should_abort:
            break

        result = await _run_single(tu, session, message_id, send)
        results.append(ToolResultBlock(
            tool_use_id=tu.id,
            content=result.content,
            is_error=result.is_error,
        ))
        await send(WSToolResult(
            tool_use_id=tu.id,
            tool_name=tu.name,
            content=result.content,
            is_error=result.is_error,
        ).model_dump())

    return results


async def _run_single(
    tu: ToolUseBlock,
    session: SessionData,
    message_id: str,
    send: SendFn,
) -> ToolResult:
    permission_mode = PermissionMode(
        session.model_config.get("permission_mode", PermissionMode.DEFAULT)
    )
    decision = check_permission(tu.name, tu.input, mode=permission_mode)

    if decision == PermissionDecision.DENY:
        logger.info("Tool %s denied by permission rules", tu.name)
        return ToolResult(
            tool_use_id=tu.id,
            content=f"Tool '{tu.name}' was denied by permission rules.",
            is_error=True,
        )

    if decision == PermissionDecision.ASK:
        approved = await _ask_user(tu, session, send)
        if not approved:
            return ToolResult(
                tool_use_id=tu.id,
                content=f"Tool '{tu.name}' was denied by the user.",
                is_error=True,
            )

    tool = tool_registry.get(tu.name)
    ctx = ToolContext(
        session_id=session.session_id,
        working_directory=session.working_directory,
        message_id=message_id,
        tool_use_id=tu.id,
        send=send,
    )

    await hook_dispatcher.dispatch(
        HookPoint.TOOL_BEFORE,
        data={"tool_name": tu.name, "tool_input": tu.input, "tool_use_id": tu.id},
        session_id=session.session_id,
    )
    try:
        result = await execute_tool(tool, ToolInput(tool_use_id=tu.id, name=tu.name, input=tu.input), ctx)
    except Exception as exc:
        await hook_dispatcher.dispatch(
            HookPoint.TOOL_ERROR,
            data={"tool_name": tu.name, "tool_input": tu.input, "error": str(exc)},
            session_id=session.session_id,
        )
        raise
    await hook_dispatcher.dispatch(
        HookPoint.TOOL_AFTER,
        data={"tool_name": tu.name, "tool_use_id": tu.id, "result": result.content, "is_error": result.is_error},
        session_id=session.session_id,
    )
    return result


async def _ask_user(tu: ToolUseBlock, session: SessionData, send: SendFn) -> bool:
    """Send a permission_request to the frontend and wait for the response."""
    tool = tool_registry.get(tu.name) if tool_registry.has(tu.name) else None
    risk = tool.risk_level.value if tool else "medium"

    event = session.register_permission_request(tu.id)
    await send(WSPermissionRequest(
        tool_use_id=tu.id,
        tool_name=tu.name,
        tool_input=tu.input,
        risk_level=risk,
    ).model_dump())

    try:
        await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT_SECS)
    except asyncio.TimeoutError:
        logger.warning("Permission request timed out for tool %s", tu.name)
        session.clear_permission(tu.id)
        return False

    decision = session.get_permission_decision(tu.id)
    session.clear_permission(tu.id)
    return decision == "approve"
