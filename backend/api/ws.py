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


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str) -> None:
    """Main WebSocket handler for a session."""
    await ws.accept()

    try:
        session = session_store.get(session_id)
    except SessionNotFoundError:
        await ws.send_json(WSError(error=f"Session not found: {session_id}", code="session_not_found").model_dump())
        await ws.close(code=4004, reason="session_not_found")
        return

    logger.info("WS connected: %s", session_id)

    async def send(msg: dict[str, Any]) -> None:
        """Send a JSON message to the WebSocket client."""
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
                await run_conversation_turn(session, msg.content, send)

            elif msg_type == "abort":
                msg_abort = WSAbort.model_validate(raw)
                logger.info("Abort requested: %s (reason=%s)", session_id, msg_abort.reason)
                session.status = SessionStatus.IDLE

            elif msg_type == "tool_permission_response":
                _perm = WSToolPermissionResponse.model_validate(raw)
                logger.info(
                    "Permission response: tool_use_id=%s decision=%s",
                    _perm.tool_use_id,
                    _perm.decision,
                )
                # TODO: feed decision into the permission gate in conversation loop

            elif msg_type == "session_config":
                cfg = WSSessionConfig.model_validate(raw)
                if cfg.model is not None:
                    session.model = cfg.model
                    logger.info("Session %s model updated to %s", session_id, cfg.model)
                if cfg.permission_mode is not None:
                    logger.info("Session %s permission mode: %s", session_id, cfg.permission_mode)

            else:
                await send(WSError(error=f"Unknown message type: {msg_type}", code="unknown_type").model_dump())

    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", session_id)
    except Exception as exc:
        logger.error("WS error for %s: %s", session_id, exc)
        try:
            await ws.send_json(WSError(error=str(exc)).model_dump())
            await ws.close(code=1011, reason="internal_error")
        except Exception:
            pass
