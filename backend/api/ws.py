"""WebSocket endpoint — /api/ws/{session_id}.

Accepts WS connections, dispatches incoming messages by type,
and streams server events back to the client.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.conversation import run_conversation_turn
from backend.schemas.messages import ContentBlock, ImageBlock, TextBlock
from backend.schemas.sessions import SessionStatus
from backend.schemas.ws import (
    WSAbort,
    WSAttachment,
    WSError,
    WSSessionConfig,
    WSToolPermissionResponse,
    WSUserMessage,
)
from backend.services.session_store import session_store
from backend.utils.errors import SessionNotFoundError

if TYPE_CHECKING:
    from backend.services.power_levels import PowerLevel

logger = logging.getLogger("tenderclaw.api.ws")
router = APIRouter()

class WSConnectionManager:
    """Manages active WebSocket connections to allow cross-request event pushing."""
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._seq_counters: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, session_id: str):
        async with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = set()
                self._seq_counters[session_id] = 0
            self.active_connections[session_id].add(ws)

    async def disconnect(self, ws: WebSocket, session_id: str):
        async with self._lock:
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(ws)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
                    self._seq_counters.pop(session_id, None)

    def next_seq(self, session_id: str) -> int:
        """Increment and return the per-session sequence counter."""
        self._seq_counters[session_id] = self._seq_counters.get(session_id, 0) + 1
        return self._seq_counters[session_id]

    def active_sessions(self) -> list[str]:
        """Return list of session IDs with active WebSocket connections."""
        return list(self.active_connections.keys())

    async def send_to_session(self, session_id: str, message: dict[str, Any]):
        """Push a message to all active clients of a session, stamping seq on sequenced events."""
        if session_id not in self.active_connections:
            return
        async with self._lock:
            if "seq" not in message and "type" in message:
                message = {**message, "seq": self.next_seq(session_id)}
        for ws in list(self.active_connections[session_id]):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Failed to send message to %s: %s", session_id, e)

ws_manager = WSConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str) -> None:
    """Main WebSocket handler for a session."""
    await ws.accept()
    await ws_manager.connect(ws, session_id)

    try:
        session = session_store.get(session_id)
    except SessionNotFoundError:
        await ws.send_json(WSError(error=f"Session not found: {session_id}", code="session_not_found").model_dump())
        await ws.close(code=4004, reason="session_not_found")
        await ws_manager.disconnect(ws, session_id)
        return

    logger.info("WS connected: %s", session_id)

    send_lock = asyncio.Lock()
    turn_task: asyncio.Task[None] | None = None

    async def send(msg: dict[str, Any]) -> None:
        async with send_lock:
            await ws.send_json(msg)

    async def run_turn_background(
        content: str | list[ContentBlock],
        power_level: PowerLevel = "medium",
    ) -> None:
        try:
            await run_conversation_turn(session, content, send, power_level=power_level)
        except asyncio.CancelledError:
            logger.info("Conversation task cancelled: %s", session_id)
            raise
        except Exception as exc:
            logger.error("Conversation task failed for %s: %s", session_id, exc, exc_info=True)
            session.status = SessionStatus.IDLE
            try:
                await send(WSError(error=str(exc)).model_dump())
            except Exception:
                logger.debug("Failed to send background turn error (connection likely closed)")

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == "user_message":
                msg = WSUserMessage.model_validate(raw)
                if session.status == SessionStatus.BUSY or (turn_task is not None and not turn_task.done()):
                    await send(WSError(error="Session is busy", code="session_busy").model_dump())
                    continue

                # Cancel any pending turn before starting a new one
                if turn_task is not None and not turn_task.done():
                    turn_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await turn_task

                # Handle image attachments as multimodal content.
                image_attachments = [
                    attachment
                    for attachment in msg.attachments
                    if attachment.type.startswith("image/") and attachment.url
                ]
                if image_attachments:
                    # Check if model supports vision BEFORE sending to OpenCode
                    from backend.services.model_router import resolve_provider

                    provider = await resolve_provider(session.model, session.model_config)
                    if provider == "opencode" and "big-pickle" in session.model.lower():
                        await send(
                            {
                                "type": "error",
                                "error": "Big Pickle non supporta immagini. Seleziona un modello vision come 'opencode/claude-sonnet-4-6' o 'opencode/gpt-5.4'.",
                                "code": "model_no_vision",
                            }
                        )
                        continue
                    session.status = SessionStatus.BUSY
                    turn_task = asyncio.create_task(
                        run_turn_background(_image_message_content(msg.content, image_attachments), msg.power_level)
                    )
                    continue

                # Run the model/tool loop in the background so this receive loop
                # can keep processing tool_permission_response and abort events.
                session.status = SessionStatus.BUSY
                turn_task = asyncio.create_task(run_turn_background(msg.content, msg.power_level))

            elif msg_type == "abort":
                msg_abort = WSAbort.model_validate(raw)
                logger.info("Abort requested: %s (reason=%s)", session_id, msg_abort.reason)
                session.should_abort = True
                session.status = SessionStatus.IDLE
                if turn_task is not None and not turn_task.done():
                    turn_task.cancel()
                await send({"type": "turn_end", "stop_reason": "aborted", "usage": {}})

            elif msg_type == "tool_permission_response":
                perm = WSToolPermissionResponse.model_validate(raw)
                logger.info(
                    "Permission response: tool_use_id=%s decision=%s",
                    perm.tool_use_id,
                    perm.decision,
                )
                # Resolve the pending permission gate in the conversation loop
                session.resolve_permission(perm.tool_use_id, perm.decision)

            elif msg_type == "session_config":
                cfg = WSSessionConfig.model_validate(raw)
                if cfg.model is not None:
                    session.model = cfg.model
                    logger.info("Session %s model updated to %s", session_id, cfg.model)
                if cfg.permission_mode is not None:
                    session.model_config["permission_mode"] = cfg.permission_mode
                    logger.info("Session %s permission mode: %s", session_id, cfg.permission_mode)

            elif msg_type == "ping":
                await send({"type": "pong"})

            else:
                await send(WSError(error=f"Unknown message type: {msg_type}", code="unknown_type").model_dump())
    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", session_id)
        if turn_task is not None and not turn_task.done():
            session.should_abort = True
            turn_task.cancel()
            with suppress(asyncio.CancelledError):
                await turn_task
        session.status = SessionStatus.IDLE
        await ws_manager.disconnect(ws, session_id)
    except Exception as exc:
        logger.error("WS error for %s: %s", session_id, exc, exc_info=True)
        if turn_task is not None and not turn_task.done():
            session.should_abort = True
            turn_task.cancel()
        session.status = SessionStatus.IDLE
        await ws_manager.disconnect(ws, session_id)
        try:
            await ws.send_json(WSError(error=str(exc)).model_dump())
        except Exception:
            logger.debug("Failed to send WS error (connection likely closed)")
        try:
            await ws.close(code=1011, reason="internal_error")
        except Exception:
            logger.debug("Failed to close WS gracefully (already closed)")


def _image_message_content(
    text: str,
    image_attachments: list[WSAttachment],
) -> list[ContentBlock]:
    """Build multimodal content blocks from pasted image attachments."""
    blocks: list[ContentBlock] = []
    if text.strip():
        blocks.append(TextBlock(text=text.strip()))
    for attachment in image_attachments:
        if not attachment.url:
            continue
        blocks.append(
            ImageBlock(
                source=attachment.url,
                mime_type=attachment.type,
                name=attachment.name or "pasted-image",
                size_bytes=attachment.size_bytes,
            )
        )

    return blocks
