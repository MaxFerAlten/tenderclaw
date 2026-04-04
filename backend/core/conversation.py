"""Conversation engine — the agentic loop.

Orchestrates: user message → API call → tool use → repeat.
Delegates streaming to core.streaming, tool execution to core.tool_runner.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Awaitable

from backend.core.streaming import StreamCollector
from backend.core.system_prompt import build_system_prompt
from backend.schemas.messages import Message, Role, ToolResultBlock
from backend.schemas.sessions import SessionStatus
from backend.services.session_store import SessionData
from backend.schemas.ws import (
    WSCostUpdate,
    WSError,
    WSMessageEnd,
    WSMessageStart,
    WSTurnEnd,
    WSTurnStart,
)
from backend.services.model_router import model_router
from backend.tools.registry import tool_registry

logger = logging.getLogger("tenderclaw.core.conversation")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
MAX_TURNS = 50


async def run_conversation_turn(
    session: SessionData,
    user_content: str,
    send: SendFn,
) -> None:
    """Run a full conversation turn (may span multiple API calls for tool use)."""
    if user_content.startswith("/team"):
        await _run_team_pipeline(session, user_content.replace("/team", "").strip(), send)
        return

    session.status = SessionStatus.BUSY
    session.should_abort = False

    if not await _validate_api_key(session, send):
        session.status = SessionStatus.IDLE
        return

    session.messages.append(Message(
        role=Role.USER,
        content=user_content,
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
    ))

    intent = await _classify(user_content, session.model)
    if intent == "implement" and len(user_content) > 100:
        await _run_team_pipeline(session, user_content, send)
        return

    await _agentic_loop(session, send)
    session.status = SessionStatus.IDLE


async def _agentic_loop(session: SessionData, send: SendFn) -> None:
    from backend.core.tool_runner import run_tool_uses

    system = build_system_prompt(
        working_directory=session.working_directory,
        append=session.system_prompt_append,
    )
    tools = tool_registry.list_api_schemas()

    for turn_number in range(1, MAX_TURNS + 1):
        if session.should_abort:
            session.should_abort = False
            await send(WSError(error="Operation cancelled by user", code="aborted").model_dump())
            return

        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        await send(WSTurnStart(turn_number=turn_number, agent_name="sisyphus").model_dump())
        await send(WSMessageStart(message_id=message_id).model_dump())

        collector = StreamCollector(message_id=message_id, send=send)

        try:
            async for event in model_router.stream_message(
                model=session.model,
                messages=_to_api_messages(session.messages),
                system=system,
                tools=tools or None,
                max_tokens=16384,
                config=session.model_config,
            ):
                if session.should_abort:
                    session.should_abort = False
                    await send(WSError(error="Operation cancelled by user", code="aborted").model_dump())
                    return
                await collector.process(event)
        except Exception as exc:
            logger.error("API error on turn %d: %s", turn_number, exc)
            await send(WSError(error=str(exc)).model_dump())
            return

        # Persist assistant message
        blocks = collector.content_blocks()
        session.messages.append(Message(
            role=Role.ASSISTANT,
            content=blocks if blocks else "".join(collector.text_parts),
            message_id=message_id,
        ))
        session.total_usage_input += collector.usage.input_tokens
        session.total_usage_output += collector.usage.output_tokens

        await send(WSMessageEnd(message_id=message_id).model_dump())
        await send(WSCostUpdate(
            input_tokens=session.total_usage_input,
            output_tokens=session.total_usage_output,
        ).model_dump())

        if collector.tool_uses and collector.stop_reason == "tool_use":
            result_blocks = await run_tool_uses(
                collector.tool_uses, session, message_id, send
            )
            session.messages.append(Message(
                role=Role.USER,
                content=result_blocks,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
            ))
            continue  # Feed results back to model

        # Turn complete
        await send(WSTurnEnd(stop_reason=collector.stop_reason, usage=collector.usage).model_dump())
        if turn_number > 1:
            _record_wisdom(
                " ".join(m.content if isinstance(m.content, str) else "" for m in session.messages[:2]),
                "agentic_loop",
            )
        return

    logger.warning("MAX_TURNS (%d) reached for session %s", MAX_TURNS, session.session_id)
    await send(WSError(error=f"Safety limit reached ({MAX_TURNS} turns)", code="max_turns").model_dump())


async def _run_team_pipeline(session: SessionData, task: str, send: SendFn) -> None:
    from backend.orchestration.pipeline import team_pipeline

    session.status = SessionStatus.BUSY
    history = _to_api_messages(session.messages[:-1])
    text_parts: list[str] = []

    async for part in team_pipeline.run_implement_pipeline(task, history, send, session=session):
        if part.get("type") == "assistant_text":
            text_parts.append(part.get("delta", ""))
        await send(part)

    if text_parts:
        session.messages.append(Message(
            role=Role.ASSISTANT,
            content="".join(text_parts),
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
        ))

    _record_wisdom(task, "pipeline")
    session.status = SessionStatus.IDLE


async def _validate_api_key(session: SessionData, send: SendFn) -> bool:
    from backend.api.config import get_session_api_key, get_session_ollama_url, get_session_lmstudio_url
    from backend.services.model_router import detect_provider

    provider = detect_provider(session.model)
    if provider == "ollama":
        session.model_config.setdefault("ollama_url", get_session_ollama_url(session.session_id))
        return True
    if provider == "lmstudio":
        session.model_config.setdefault("lmstudio_url", get_session_lmstudio_url(session.session_id))
        return True

    key = get_session_api_key(provider, session.session_id)
    if not key:
        await send(WSError(
            error=f"No API key for '{provider}'. Go to Settings and add your key.",
            code="api_key_missing",
        ).model_dump())
        return False
    return True


async def _classify(prompt: str, model: str = "") -> str:
    try:
        from backend.orchestration.intent_gate import classify_intent
        intent = await classify_intent(prompt, session_model=model)
        return intent.value
    except Exception:
        return "implement"


def _record_wisdom(task: str, task_type: str) -> None:
    try:
        from backend.memory.wisdom import WisdomItem, wisdom_store
        wisdom_store.add(WisdomItem(
            id=f"w_{uuid.uuid4().hex[:8]}",
            task_type=task_type,
            description=task[:200],
            solution_pattern=f"Completed via {task_type}",
        ))
    except Exception as exc:
        logger.warning("Failed to record wisdom: %s", exc)


def _to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
    from backend.schemas.messages import TextBlock, ToolResultBlock, ToolUseBlock

    api: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg.content, str):
            api.append({"role": msg.role.value, "content": msg.content})
        elif isinstance(msg.content, list):
            blocks = []
            for b in msg.content:
                if isinstance(b, TextBlock):
                    blocks.append({"type": "text", "text": b.text})
                elif isinstance(b, ToolUseBlock):
                    blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
                elif isinstance(b, ToolResultBlock):
                    blocks.append({"type": "tool_result", "tool_use_id": b.tool_use_id,
                                   "content": b.content, "is_error": b.is_error})
            api.append({"role": msg.role.value, "content": blocks})
    return api
