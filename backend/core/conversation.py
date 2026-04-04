"""Conversation engine — the agentic loop.

Implements the core cycle: user message -> API call -> tool use -> repeat.
This is the heart of TenderClaw, equivalent to Claude Code's query.ts + QueryEngine.ts
but split cleanly across focused modules.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Awaitable

from backend.core.system_prompt import build_system_prompt
from backend.schemas.messages import (
    ContentBlockType,
    Message,
    Role,
    TextBlock,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
)
from backend.schemas.sessions import SessionState, SessionStatus
from backend.schemas.tools import ToolInput, ToolResult
from backend.schemas.ws import (
    WSAssistantText,
    WSAssistantThinking,
    WSCostUpdate,
    WSError,
    WSMessageEnd,
    WSMessageStart,
    WSPermissionRequest,
    WSToolProgress,
    WSToolResult,
    WSToolUseStart,
    WSTurnEnd,
    WSTurnStart,
)
from backend.services.model_router import model_router
from backend.tools.base import ToolContext
from backend.tools.execution import execute_tool
from backend.tools.registry import tool_registry

logger = logging.getLogger("tenderclaw.core.conversation")

# Type for the WebSocket send function
SendFn = Callable[[dict[str, Any]], Awaitable[None]]

MAX_TURNS = 50  # Safety limit for agentic loop


async def run_conversation_turn(
    session: SessionState,
    user_content: str,
    send: SendFn,
) -> None:
    """Run a full conversation turn (may involve multiple API calls for tool use).

    Args:
        session: Current session state (mutated in place).
        user_content: The user's message text.
        send: Async function to send WebSocket messages to the frontend.
    """
    # Handle orchestrator commands
    if user_content.startswith("/team"):
        from backend.orchestration.pipeline import team_pipeline
        task = user_content.replace("/team", "").strip()
        session.status = SessionStatus.BUSY

        history = _to_api_messages(session.messages[:-1])
        pipeline_text: list[str] = []

        async for part in team_pipeline.run_implement_pipeline(task, history, send):
            event_type = part.get("type", "")
            if event_type == "assistant_text":
                pipeline_text.append(part.get("delta", ""))
            await send(part)

        # Store pipeline result as assistant message
        if pipeline_text:
            msg = Message(
                role=Role.ASSISTANT,
                content="".join(pipeline_text),
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
            )
            session.messages.append(msg)

        # Record wisdom from successful pipeline execution
        _record_wisdom(task, "pipeline")

        session.status = SessionStatus.IDLE
        return

    session.status = SessionStatus.BUSY

    # Add user message to history
    user_msg = Message(
        role=Role.USER,
        content=user_content,
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
    )
    session.messages.append(user_msg)

    from backend.orchestration.intent_gate import classify_intent, Intent
    intent = await classify_intent(user_content)
    logger.info("Classified intent for %s: %s", session.session_id, intent)

    # Build API messages from history
    system = build_system_prompt(
        working_directory=session.working_directory,
        append=session.system_prompt_append,
    )
    tools = tool_registry.list_api_schemas()
    turn_number = 0

    while turn_number < MAX_TURNS:
        turn_number += 1
        await send(WSTurnStart(
            turn_number=turn_number,
            agent_name="sisyphus"
        ).model_dump())

        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        await send(WSMessageStart(message_id=message_id).model_dump())

        # Convert session messages to API format
        api_messages = _to_api_messages(session.messages)

        # Stream the API response
        text_parts: list[str] = []
        tool_uses: list[ToolUseBlock] = []
        current_tool_input_json = ""
        current_tool_name = ""
        current_tool_id = ""
        stop_reason = "end_turn"
        turn_usage = TokenUsage()

        try:
            async for event in model_router.stream_message(
                model=session.model,
                messages=api_messages,
                system=system,
                tools=tools if tools else None,
                max_tokens=16384,
            ):
                event_type = event.get("type", "")

                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    block_type = block.get("type", "")

                    if block_type == "tool_use":
                        current_tool_id = block.get("id", "")
                        current_tool_name = block.get("name", "")
                        current_tool_input_json = ""
                        await send(WSToolUseStart(
                            tool_use_id=current_tool_id,
                            tool_name=current_tool_name,
                            message_id=message_id,
                        ).model_dump())

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type", "")

                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        text_parts.append(text)
                        await send(WSAssistantText(
                            delta=text,
                            message_id=message_id,
                        ).model_dump())

                    elif delta_type == "thinking_delta":
                        thinking = delta.get("thinking", "")
                        await send(WSAssistantThinking(
                            delta=thinking,
                            message_id=message_id,
                        ).model_dump())

                    elif delta_type == "input_json_delta":
                        current_tool_input_json += delta.get("partial_json", "")

                elif event_type == "content_block_stop":
                    if current_tool_id and current_tool_name:
                        try:
                            parsed_input = json.loads(current_tool_input_json) if current_tool_input_json else {}
                        except json.JSONDecodeError:
                            parsed_input = {}

                        tool_uses.append(ToolUseBlock(
                            id=current_tool_id,
                            name=current_tool_name,
                            input=parsed_input,
                        ))
                        current_tool_id = ""
                        current_tool_name = ""
                        current_tool_input_json = ""

                elif event_type == "message_delta":
                    delta = event.get("delta", {})
                    stop_reason = delta.get("stop_reason", "end_turn") or "end_turn"

                elif event_type == "usage":
                    turn_usage = event.get("usage", TokenUsage())

        except Exception as exc:
            logger.error("API error during turn %d: %s", turn_number, exc)
            await send(WSError(error=str(exc)).model_dump())
            break

        # Build assistant message from collected blocks
        content_blocks: list[TextBlock | ToolUseBlock] = []
        if text_parts:
            content_blocks.append(TextBlock(text="".join(text_parts)))
        content_blocks.extend(tool_uses)

        assistant_msg = Message(
            role=Role.ASSISTANT,
            content=content_blocks if content_blocks else "".join(text_parts),
            message_id=message_id,
        )
        session.messages.append(assistant_msg)

        # Update usage
        if isinstance(turn_usage, TokenUsage):
            session.total_usage.input_tokens += turn_usage.input_tokens
            session.total_usage.output_tokens += turn_usage.output_tokens

        await send(WSMessageEnd(message_id=message_id).model_dump())

        # If there are tool uses, execute them and continue the loop
        if tool_uses and stop_reason == "tool_use":
            tool_result_blocks: list[ToolResultBlock] = []

            for tu in tool_uses:
                tool = tool_registry.get(tu.name)
                ctx = ToolContext(
                    session_id=session.session_id,
                    working_directory=session.working_directory,
                    message_id=message_id,
                    tool_use_id=tu.id,
                    send=send,
                )

                result = await execute_tool(
                    tool,
                    ToolInput(tool_use_id=tu.id, name=tu.name, input=tu.input),
                    ctx,
                )

                await send(WSToolResult(
                    tool_use_id=tu.id,
                    tool_name=tu.name,
                    content=result.content,
                    is_error=result.is_error,
                ).model_dump())

                tool_result_blocks.append(ToolResultBlock(
                    tool_use_id=tu.id,
                    content=result.content,
                    is_error=result.is_error,
                ))

            # Add tool results as a user message (Anthropic format)
            tool_result_msg = Message(
                role=Role.USER,
                content=tool_result_blocks,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
            )
            session.messages.append(tool_result_msg)

            # Continue the loop — API will process tool results
            continue

        # No tool use — turn is complete
        await send(WSTurnEnd(
            stop_reason=stop_reason,
            usage=turn_usage if isinstance(turn_usage, TokenUsage) else TokenUsage(),
        ).model_dump())

        # Record wisdom from successful multi-turn tool execution
        if turn_number > 1:
            _record_wisdom(user_content, "agentic_loop")

        break

    session.status = SessionStatus.IDLE


def _record_wisdom(task: str, task_type: str) -> None:
    """Record a wisdom item after successful task completion."""
    try:
        from backend.memory.wisdom import wisdom_store, WisdomItem
        item = WisdomItem(
            id=f"w_{uuid.uuid4().hex[:8]}",
            task_type=task_type,
            description=task[:200],
            solution_pattern=f"Completed via {task_type} pipeline",
        )
        wisdom_store.add(item)
    except Exception as exc:
        logger.warning("Failed to record wisdom: %s", exc)


def _to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert internal Messages to the Anthropic API format."""
    api_msgs: list[dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg.content, str):
            api_msgs.append({"role": msg.role.value, "content": msg.content})
        elif isinstance(msg.content, list):
            blocks: list[dict[str, Any]] = []
            for block in msg.content:
                if isinstance(block, TextBlock):
                    blocks.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolUseBlock):
                    blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                elif isinstance(block, ToolResultBlock):
                    blocks.append({
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "content": block.content,
                        "is_error": block.is_error,
                    })
            api_msgs.append({"role": msg.role.value, "content": blocks})

    return api_msgs
