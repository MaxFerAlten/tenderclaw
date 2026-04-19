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
from backend.schemas.messages import ContentBlock, ImageBlock, Message, Role, TextBlock, ToolResultBlock
from backend.schemas.sessions import SessionStatus
from backend.services.session_store import SessionData, session_store
from backend.hooks.dispatcher import hook_dispatcher
from backend.schemas.hooks import HookPoint
from backend.schemas.ws import (
    WSCostUpdate,
    WSError,
    WSMessageEnd,
    WSMessageStart,
    WSNotification,
    WSTurnEnd,
    WSTurnStart,
)
from backend.services.model_router import model_router
from backend.services.cost_calculator import compute_cost
from backend.services.cost_tracker import CostTracker
from backend.services.notifications import (
    NotificationCategory,
    NotificationLevel,
    notification_service,
)
from backend.services.power_levels import PowerLevel
from backend.tools.registry import tool_registry
from backend.telemetry.tracing import get_tracer, add_span_attributes, SpanKind
from backend.telemetry.metrics import Metrics
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("tenderclaw.core.conversation")

tracer = get_tracer("tenderclaw.conversation")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
MAX_TURNS = 50

IMAGE_RESPONSE_INSTRUCTIONS = """\
## Image Analysis Instructions
The latest user message includes one or more image attachments.
- Treat attached images as first-class input; inspect visible text, layout, state, UI controls, errors, and context.
- Answer in the same language as the user's text. If there is no text, infer the language from the recent conversation.
- Do not narrate private reasoning or start with meta-analysis such as "The user is asking me".
- For screenshots, ground conclusions in concrete visible evidence and call out uncertainty when text is unreadable.
- Use tools only when the user explicitly asks you to inspect files, run commands, or fetch external information.
"""


async def run_conversation_turn(
    session: SessionData,
    user_content: str | list[ContentBlock],
    send: SendFn,
    power_level: PowerLevel = "medium",
) -> None:
    """Run a full conversation turn (may span multiple API calls for tool use)."""
    Metrics.increment_request({"session_id": session.session_id})

    with tracer.start_as_current_span(
        "conversation.turn",
        kind=SpanKind.INTERNAL,
        attributes={
            "session_id": session.session_id,
            "user_id": getattr(session, "user_id", None),
            "model": session.model,
            "working_directory": session.working_directory,
        },
    ) as span:
        try:
            await _run_conversation_turn_impl(session, user_content, send, power_level=power_level)
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


async def _run_conversation_turn_impl(
    session: SessionData,
    user_content: str | list[ContentBlock],
    send: SendFn,
    power_level: PowerLevel = "medium",
) -> None:
    """Internal implementation of conversation turn."""
    user_text = _content_text(user_content)
    effective_prompt = user_text or _image_fallback_prompt(user_content)
    force_team_pipeline = user_text.startswith("/team")

    await hook_dispatcher.dispatch(
        HookPoint.SESSION_START,
        data={"user_content": effective_prompt},
        session_id=session.session_id,
    )

    session.status = SessionStatus.BUSY
    session.should_abort = False

    if not await _validate_api_key(session, send):
        session.status = SessionStatus.IDLE
        return

    # Extract and persist images from user message (if any)
    if isinstance(user_content, list):
        try:
            from backend.services.image_store import extract_and_save_images

            _image_refs = extract_and_save_images(session.session_id, user_content)
            logger.info("Persisted %d image(s) for session %s", len(_image_refs), session.session_id)
        except Exception as exc:
            logger.warning("Image persistence failed for session %s: %s", session.session_id, exc)

    session.messages.append(
        Message(
            role=Role.USER,
            content=user_content,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
        )
    )
    await hook_dispatcher.dispatch(
        HookPoint.MESSAGE_USER_BEFORE,
        data={"content": effective_prompt},
        session_id=session.session_id,
    )

    if force_team_pipeline:
        await _run_team_pipeline(session, user_text.removeprefix("/team").strip(), send)
        return

    intent = await _classify(effective_prompt, session.model)
    add_span_attributes({"intent": intent})

    # Only auto-route to the team pipeline for Anthropic-backed models.
    # OpenCode / Ollama / gpt4free / other providers run the standard agentic
    # loop — the team pipeline uses Anthropic sub-agents internally.
    # Honour the user's explicit provider selection: e.g. a user running
    # claude-3-5-sonnet through gpt4free should NOT trigger the team pipeline.
    from backend.services.model_router import resolve_provider

    _provider = await resolve_provider(session.model, session.model_config)
    _anthropic_native = _provider == "anthropic"
    if _anthropic_native and intent == "implement" and len(effective_prompt) > 100:
        await _run_team_pipeline(session, effective_prompt, send)
        return

    try:
        with tracer.start_as_current_span(
            "conversation.agentic_loop",
            kind=SpanKind.INTERNAL,
            attributes={"model": session.model},
        ):
            await _agentic_loop(session, send, power_level=power_level)
    except Exception as exc:
        logger.error("Unhandled error in agentic loop for %s: %s", session.session_id, exc, exc_info=True)
        Metrics.increment_error("agentic_loop_error", {"session_id": session.session_id})
        notification_service.create(
            title="Error in conversation",
            body=str(exc)[:200],
            level=NotificationLevel.ERROR,
            category=NotificationCategory.SYSTEM,
            session_id=session.session_id,
        )
        try:
            await send(WSError(error=str(exc)).model_dump())
        except Exception:
            logger.debug("Failed to send error to client (connection likely closed)")
    finally:
        session.status = SessionStatus.IDLE
        session_store.persist(session)
        # Archive complete session to workspace for long-term storage
        try:
            from backend.services.session_archiver import archive_session

            _serialize_for_archive = []
            for msg in session.messages:
                if hasattr(msg, "model_dump"):
                    _serialize_for_archive.append(msg.model_dump())
                elif isinstance(msg, dict):
                    _serialize_for_archive.append(msg)
                else:
                    _serialize_for_archive.append({"role": str(msg.role), "content": str(msg.content)})

            archive_session(
                session.session_id,
                {
                    "session_id": session.session_id,
                    "status": session.status.value if hasattr(session.status, "value") else str(session.status),
                    "model": session.model,
                    "created_at": session.created_at.isoformat() if hasattr(session, "created_at") else "",
                    "messages": _serialize_for_archive,
                    "total_usage_input": session.total_usage_input,
                    "total_usage_output": session.total_usage_output,
                    "total_cost_usd": session.total_cost_usd,
                },
            )
        except Exception as exc:
            logger.warning("Archive failed for session %s: %s", session.session_id, exc)

    await hook_dispatcher.dispatch(
        HookPoint.SESSION_END,
        data={},
        session_id=session.session_id,
    )


async def _agentic_loop(
    session: SessionData,
    send: SendFn,
    power_level: PowerLevel = "medium",
) -> None:
    from backend.core.tool_runner import run_tool_uses
    from backend.memory.memory_manager import memory_manager
    from backend.memory.memdir import get_memory_directory

    # Extract user content from the last user message for skill matching
    user_content = ""
    for msg in reversed(session.messages):
        if msg.role == Role.USER:
            user_content = _message_text(msg)
            break

    with tracer.start_as_current_span(
        "conversation.agentic_loop",
        kind=SpanKind.INTERNAL,
        attributes={
            "session_id": session.session_id,
            "model": session.model,
        },
    ) as loop_span:
        await _agentic_loop_impl(session, send, loop_span, user_content=user_content, power_level=power_level)


async def _agentic_loop_impl(
    session: SessionData,
    send: SendFn,
    parent_span,
    *,
    user_content: str = "",
    power_level: PowerLevel = "medium",
) -> None:
    from backend.core.tool_runner import run_tool_uses
    from backend.memory.memory_manager import memory_manager
    from backend.memory.memdir import get_memory_directory

    import time

    turn_start_time = time.perf_counter()

    # Retrieve relevant past wisdom for this conversation
    try:
        wisdom_context = memory_manager.build_context_for_prompt(_to_api_messages(session.messages), limit=5)
    except Exception:
        wisdom_context = ""

    # Retrieve MEMORY.md context
    try:
        memdir = get_memory_directory(session.working_directory)
        memdir.scan_and_index()
        context_text = " ".join(_message_text(m) for m in session.messages[-4:])
        memory_context = memdir.format_for_system_prompt(context_text, limit=5)
    except Exception:
        memory_context = ""

    # Skill trigger matching — inject matched skill context into the prompt
    skill_append = ""
    try:
        from backend.core.skills import match_trigger

        matched = match_trigger(user_content)
        if matched:
            skill = matched[0]
            skill_append = (
                f"\n## Active Skill: {skill.name}\n"
                f"The user's message matched the '{skill.name}' skill (trigger: {skill.trigger}).\n"
                f"Follow the instructions in the skill file at: {skill.path}\n"
            )
            logger.info("Skill trigger matched: %s for input: %.60s", skill.name, user_content)
    except Exception as exc:
        logger.debug("Skill trigger matching skipped: %s", exc)

    image_append = IMAGE_RESPONSE_INSTRUCTIONS if _latest_user_has_image(session.messages) else ""
    combined_append = "\n".join(
        part for part in (session.system_prompt_append or "", skill_append, image_append) if part
    )

    system = build_system_prompt(
        working_directory=session.working_directory,
        append=combined_append,
        wisdom_context=wisdom_context,
        memory_context=memory_context,
    )
    tools = tool_registry.list_api_schemas()
    empty_response_retries = 0

    for turn_number in range(1, MAX_TURNS + 1):
        if session.should_abort:
            session.should_abort = False
            await hook_dispatcher.dispatch(
                HookPoint.TURN_END,
                data={"turn_number": turn_number, "agent": "sisyphus", "stop_reason": "aborted"},
                session_id=session.session_id,
            )
            await send(WSError(error="Operation cancelled by user", code="aborted").model_dump())
            return

        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        await hook_dispatcher.dispatch(
            HookPoint.TURN_START,
            data={"turn_number": turn_number, "agent": "sisyphus"},
            session_id=session.session_id,
        )
        await send(WSTurnStart(turn_number=turn_number, agent_name="sisyphus").model_dump())
        await send(WSMessageStart(message_id=message_id).model_dump())

        if turn_number == 1:
            notif = notification_service.create(
                title="Turn started",
                body=f"Sisyphus processing (model: {session.model})",
                level=NotificationLevel.INFO,
                category=NotificationCategory.AGENT,
                agent_name="sisyphus",
                session_id=session.session_id,
                auto_dismiss_ms=3000,
            )
            await send(
                WSNotification(
                    id=notif.id,
                    level=notif.level.value,
                    category=notif.category.value,
                    title=notif.title,
                    body=notif.body,
                    agent_name=notif.agent_name,
                    auto_dismiss_ms=notif.auto_dismiss_ms,
                ).model_dump()
            )

        collector = StreamCollector(message_id=message_id, send=send)

        stream_config = dict(session.model_config)
        stream_config["session_id"] = session.session_id

        try:
            async for event in model_router.stream_message(
                model=session.model,
                messages=_to_api_messages(session.messages),
                system=system,
                tools=tools or None,
                max_tokens=16384,
                config=stream_config,
                power_level=power_level,
            ):
                if session.should_abort:
                    session.should_abort = False
                    await hook_dispatcher.dispatch(
                        HookPoint.TURN_END,
                        data={"turn_number": turn_number, "agent": "sisyphus", "stop_reason": "aborted"},
                        session_id=session.session_id,
                    )
                    await send(WSError(error="Operation cancelled by user", code="aborted").model_dump())
                    return
                await collector.process(event)
        except Exception as exc:
            logger.error("API error on turn %d: %s", turn_number, exc)
            await hook_dispatcher.dispatch(
                HookPoint.TURN_END,
                data={"turn_number": turn_number, "agent": "sisyphus", "stop_reason": "error"},
                session_id=session.session_id,
            )
            await send(WSError(error=str(exc)).model_dump())
            return

        # Persist assistant message
        blocks = collector.content_blocks()
        visible_text = "".join(collector.text_parts)
        if not blocks and not visible_text and not collector.tool_uses:
            logger.warning(
                "Empty assistant turn from model=%s session=%s turn=%d stop_reason=%s",
                session.model,
                session.session_id,
                turn_number,
                collector.stop_reason,
            )
            await send(WSMessageEnd(message_id=message_id).model_dump())

            if empty_response_retries < 1:
                empty_response_retries += 1
                session.messages.append(
                    Message(
                        role=Role.USER,
                        content=(
                            "Your previous turn produced no visible answer and no tool call. "
                            "Continue now with either a real tool call or a concise final answer. "
                            "Do not emit hidden-thinking tags or private scratchpad text."
                        ),
                        message_id=f"msg_{uuid.uuid4().hex[:8]}",
                    )
                )
                continue

            await send(
                WSError(
                    error=(
                        "LM Studio ha restituito una risposta vuota dopo i tool. "
                        "Il task è stato fermato per evitare una chiusura silenziosa."
                    ),
                    code="empty_model_response",
                ).model_dump()
            )
            await send(WSTurnEnd(stop_reason="empty_model_response", usage=collector.usage).model_dump())
            return

        assistant_msg = Message(
            role=Role.ASSISTANT,
            content=blocks if blocks else visible_text,
            message_id=message_id,
        )
        session.messages.append(assistant_msg)

        turn_input = collector.usage.input_tokens
        turn_output = collector.usage.output_tokens
        session.total_usage_input += turn_input
        session.total_usage_output += turn_output
        turn_cost = compute_cost(session.model, turn_input, turn_output)
        session.total_cost_usd = getattr(session, "total_cost_usd", 0.0) + turn_cost

        CostTracker.record_usage(
            session_id=session.session_id,
            model=session.model,
            input_tokens=turn_input,
            output_tokens=turn_output,
            cost_usd=turn_cost,
            api_duration_ms=getattr(collector.usage, "api_duration_ms", 0.0),
        )

        Metrics.record_tokens(turn_input, turn_output, {"model": session.model, "turn": turn_number})
        Metrics.record_cost(turn_cost, session.model)

        await hook_dispatcher.dispatch(
            HookPoint.MESSAGE_ASSISTANT_AFTER,
            data={"message_id": message_id, "content": assistant_msg.content, "stop_reason": collector.stop_reason},
            session_id=session.session_id,
        )

        await send(WSMessageEnd(message_id=message_id).model_dump())

        await hook_dispatcher.dispatch(
            HookPoint.TURN_END,
            data={"turn_number": turn_number, "agent": "sisyphus", "stop_reason": collector.stop_reason},
            session_id=session.session_id,
        )

        if collector.tool_uses:
            result_blocks = await run_tool_uses(collector.tool_uses, session, message_id, send)
            session.messages.append(
                Message(
                    role=Role.USER,
                    content=result_blocks,
                    message_id=f"msg_{uuid.uuid4().hex[:8]}",
                )
            )
            continue  # Feed results back to model

        # Turn complete
        await send(WSTurnEnd(stop_reason=collector.stop_reason, usage=collector.usage).model_dump())
        if turn_number > 1:
            _record_wisdom(
                " ".join(_message_text(m) for m in session.messages[:2]),
                "agentic_loop",
            )
            _log_memory_activity(session, turn_number)
        return

    logger.warning("MAX_TURNS (%d) reached for session %s", MAX_TURNS, session.session_id)
    await send(WSError(error=f"Safety limit reached ({MAX_TURNS} turns)", code="max_turns").model_dump())


async def _run_team_pipeline(session: SessionData, task: str, send: SendFn) -> None:
    from backend.orchestration.pipeline import team_pipeline

    session.status = SessionStatus.BUSY
    history = _to_api_messages(session.messages[:-1])
    text_parts: list[str] = []

    await hook_dispatcher.dispatch(
        HookPoint.AGENT_DELEGATE_BEFORE,
        data={"task": task, "agent": "team"},
        session_id=session.session_id,
    )

    try:
        async for part in team_pipeline.run_implement_pipeline(task, history, send, session=session):
            if part.get("type") == "assistant_text":
                text_parts.append(part.get("delta", ""))
            await send(part)

        await hook_dispatcher.dispatch(
            HookPoint.AGENT_DELEGATE_AFTER,
            data={"task": task, "agent": "team"},
            session_id=session.session_id,
        )

        if text_parts:
            session.messages.append(
                Message(
                    role=Role.ASSISTANT,
                    content="".join(text_parts),
                    message_id=f"msg_{uuid.uuid4().hex[:8]}",
                )
            )

        _record_wisdom(task, "pipeline")
    except Exception as exc:
        logger.error("Team pipeline error for %s: %s", session.session_id, exc, exc_info=True)
        try:
            await send(WSError(error=str(exc)).model_dump())
        except Exception:
            logger.debug("Failed to send pipeline error to client (connection likely closed)")
    finally:
        session.status = SessionStatus.IDLE
        session_store.persist(session)
        # Archive complete session to workspace for long-term storage
        try:
            from backend.services.session_archiver import archive_session

            _serialize_for_archive = []
            for msg in session.messages:
                if hasattr(msg, "model_dump"):
                    _serialize_for_archive.append(msg.model_dump())
                elif isinstance(msg, dict):
                    _serialize_for_archive.append(msg)
                else:
                    _serialize_for_archive.append({"role": str(msg.role), "content": str(msg.content)})

            archive_session(
                session.session_id,
                {
                    "session_id": session.session_id,
                    "status": session.status.value if hasattr(session.status, "value") else str(session.status),
                    "model": session.model,
                    "created_at": session.created_at.isoformat() if hasattr(session, "created_at") else "",
                    "messages": _serialize_for_archive,
                    "total_usage_input": session.total_usage_input,
                    "total_usage_output": session.total_usage_output,
                    "total_cost_usd": session.total_cost_usd,
                },
            )
        except Exception as exc:
            logger.warning("Archive failed for session %s: %s", session.session_id, exc)

    await hook_dispatcher.dispatch(
        HookPoint.SESSION_END,
        data={},
        session_id=session.session_id,
    )


async def _validate_api_key(session: SessionData, send: SendFn) -> bool:
    from backend.api.config import (
        get_session_api_key,
        get_session_ollama_url,
        get_session_lmstudio_url,
        get_session_llamacpp_url,
        get_session_gpt4free_url,
        _global_config,
    )
    from backend.services.model_router import resolve_provider

    # Build an effective config so resolve_provider can honour `selected_provider`
    # both at session and global level (the global dict is the fallback used
    # when the session hasn't explicitly stored one yet).
    _effective_cfg = dict(session.model_config)
    if not _effective_cfg.get("selected_provider") and _global_config.get("selected_provider"):
        _effective_cfg["selected_provider"] = _global_config["selected_provider"]

    provider = await resolve_provider(session.model, _effective_cfg)

    _KEYLESS_PROVIDERS = {"ollama", "lmstudio", "llamacpp", "gpt4free"}
    if provider in _KEYLESS_PROVIDERS:
        if provider == "ollama":
            session.model_config.setdefault("ollama_url", get_session_ollama_url(session.session_id))
        elif provider == "lmstudio":
            session.model_config.setdefault("lmstudio_url", get_session_lmstudio_url(session.session_id))
        elif provider == "llamacpp":
            session.model_config.setdefault("llamacpp_url", get_session_llamacpp_url(session.session_id))
        elif provider == "gpt4free":
            session.model_config.setdefault("gpt4free_url", get_session_gpt4free_url(session.session_id))
        return True

    # deepseek routes through openrouter
    lookup_provider = "openrouter" if provider == "deepseek" else provider

    from backend.api.config import _PROVIDER_KEY_MAP

    key_field = _PROVIDER_KEY_MAP.get(lookup_provider)
    key = get_session_api_key(lookup_provider, session.session_id)
    if key:
        if key_field:
            session.model_config[key_field] = key
        session.model_config["session_id"] = session.session_id
        return True

    await send(
        WSError(
            error=f"No API key for '{provider}'. Go to Settings and add your key.",
            code="api_key_missing",
        ).model_dump()
    )
    return False


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

        wisdom_store.add(
            WisdomItem(
                id=f"w_{uuid.uuid4().hex[:8]}",
                task_type=task_type,
                description=task[:200],
                solution_pattern=f"Completed via {task_type}",
            )
        )
    except Exception as exc:
        logger.warning("Failed to record wisdom: %s", exc)


def _log_memory_activity(session: SessionData, turn: int) -> None:
    """Log conversation activity to memory."""
    try:
        from backend.memory.memdir import get_memory_directory

        memdir = get_memory_directory(session.working_directory)
        memdir.log_activity(f"Turn {turn}: {len(session.messages)} messages")
    except Exception as exc:
        logger.debug("Failed to log memory activity: %s", exc)


def _to_api_messages(messages: list[Message]) -> list[dict[str, Any]]:
    from backend.schemas.messages import ImageBlock, TextBlock, ToolResultBlock, ToolUseBlock

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
                    blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": b.tool_use_id,
                            "content": b.content,
                            "is_error": b.is_error,
                        }
                    )
                elif isinstance(b, ImageBlock):
                    blocks.append({"type": "image_url", "image_url": {"url": b.source}})
            api.append({"role": msg.role.value, "content": blocks})
    return api


def _content_text(content: str | list[ContentBlock]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(block.text for block in content if isinstance(block, TextBlock)).strip()


def _message_text(message: Message) -> str:
    return _content_text(message.content)


def _latest_user_has_image(messages: list[Message]) -> bool:
    for message in reversed(messages):
        if message.role != Role.USER:
            continue
        return isinstance(message.content, list) and any(isinstance(block, ImageBlock) for block in message.content)
    return False


def _image_fallback_prompt(content: str | list[ContentBlock]) -> str:
    if isinstance(content, str):
        return content
    image_count = sum(1 for block in content if isinstance(block, ImageBlock))
    if image_count == 1:
        return "Analyze the attached image."
    if image_count > 1:
        return f"Analyze the {image_count} attached images."
    return ""
