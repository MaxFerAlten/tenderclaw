"""WebSocket endpoint — /api/ws/{session_id}.

Accepts WS connections, dispatches incoming messages by type,
and streams server events back to the client.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.conversation import run_conversation_turn
from backend.schemas.sessions import SessionStatus
from backend.schemas.ws import (
    WSAbort,
    WSError,
    WSSessionConfig,
    WSToolPermissionResponse,
    WSUserMessage,
)
from backend.services.session_store import session_store
from backend.utils.errors import SessionNotFoundError

logger = logging.getLogger("tenderclaw.api.ws")
router = APIRouter()

class WSConnectionManager:
    """Manages active WebSocket connections to allow cross-request event pushing."""
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}

    def connect(self, ws: WebSocket, session_id: str):
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(ws)

    def disconnect(self, ws: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(ws)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_to_session(self, session_id: str, message: dict[str, Any]):
        """Push a message to all active clients of a session."""
        if session_id in self.active_connections:
            for ws in self.active_connections[session_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.warning("Failed to send message to %s: %s", session_id, e)

ws_manager = WSConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str) -> None:
    """Main WebSocket handler for a session."""
    await ws.accept()
    ws_manager.connect(ws, session_id)

    try:
        session = session_store.get(session_id)
    except SessionNotFoundError:
        await ws.send_json(WSError(error=f"Session not found: {session_id}", code="session_not_found").model_dump())
        await ws.close(code=4004, reason="session_not_found")
        ws_manager.disconnect(ws, session_id)
        return

    logger.info("WS connected: %s", session_id)

    async def send(msg: dict[str, Any]) -> None:
        await ws.send_json(msg)

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == "user_message":
                msg = WSUserMessage.model_validate(raw)
                if session.status == SessionStatus.BUSY:
                    await send(WSError(error="Session is busy", code="session_busy").model_dump())
                    continue

                # Handle image attachments via Looker agent
                attachments = raw.get("attachments", [])
                image_attachments = [a for a in attachments if a.get("type", "").startswith("image/")]
                if image_attachments:
                    # Check if model supports vision BEFORE sending to OpenCode
                    from backend.services.model_router import detect_provider

                    provider = await detect_provider(session.model)
                    if provider == "opencode" and "big-pickle" in session.model.lower():
                        await send(
                            {
                                "type": "error",
                                "error": "Big Pickle non supporta immagini. Seleziona un modello vision come 'opencode/claude-sonnet-4-6' o 'opencode/gpt-5.4'.",
                                "code": "model_no_vision",
                            }
                        )
                        return
                    await _handle_image_message(session, msg.content, image_attachments, send)
                    continue

                await run_conversation_turn(session, msg.content, send)

            elif msg_type == "abort":
                msg_abort = WSAbort.model_validate(raw)
                logger.info("Abort requested: %s (reason=%s)", session_id, msg_abort.reason)
                session.should_abort = True
                session.status = SessionStatus.IDLE
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
        ws_manager.disconnect(ws, session_id)
    except Exception as exc:
        logger.error("WS error for %s: %s", session_id, exc, exc_info=True)
        ws_manager.disconnect(ws, session_id)
        try:
            await ws.send_json(WSError(error=str(exc)).model_dump())
        except Exception:
            logger.debug("Failed to send WS error (connection likely closed)")
        try:
            await ws.close(code=1011, reason="internal_error")
        except Exception:
            logger.debug("Failed to close WS gracefully (already closed)")


async def _handle_image_message(
    session: Any,
    text: str,
    image_attachments: list[dict],
    send: Any,
) -> None:
    """Route image messages to the Looker agent."""
    from backend.services.model_router import detect_provider

    provider = await detect_provider(session.model)

    if provider == "opencode" and "big-pickle" in session.model.lower():
        await send(
            {
                "type": "error",
                "error": "Big Pickle non supporta immagini. Seleziona un modello vision come 'opencode/claude-sonnet-4-6' o 'opencode/gpt-5.4' nelle impostazioni.",
                "code": "model_no_vision",
            }
        )
        return

    from backend.core.conversation import run_conversation_turn

    image_refs = "\n".join(
        f"[Image: {a.get('name', 'attachment')} ({a.get('type', 'image')})]"
        + (f" URL: {a['url']}" if a.get("url") else "")
        for a in image_attachments
    )
    combined = f"{text}\n\n{image_refs}".strip() if text else image_refs

    original_model = session.model
    session.model_config["agent_override"] = "looker"
    try:
        await run_conversation_turn(session, combined, send)
    finally:
        session.model_config.pop("agent_override", None)
