"""OpenClaw Relay API — Accept external webhook tasks and route to active sessions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.api.ws import ws_manager
from backend.core.conversation import run_conversation_turn
from backend.services.session_store import session_store
from backend.utils.errors import SessionNotFoundError

logger = logging.getLogger("tenderclaw.api.relay")

router = APIRouter()


class RelayTaskRequest(BaseModel):
    """A task or message pushed from an external system."""

    content: str
    sender: str = "external_relay"
    agent_override: str | None = None
    trigger_evaluation: bool = True


class RelayTaskResponse(BaseModel):
    status: str
    session_id: str
    message: str


@router.post("/{session_id}", response_model=RelayTaskResponse)
async def push_task(
    session_id: str,
    request: RelayTaskRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """Push a message or task to an active session from an external system.
    
    If trigger_evaluation is True, it will automatically instruct the session's agent
    to answer the task, broadcasting the response real-time to connected UI clients.
    """
    try:
        session = session_store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Forward the message specifically as a system notification or standard message
    # To keep it simple, we use the ws_manager to push a text chunk directly if we want
    logger.info("Relay task received for %s from %s", session_id, request.sender)

    combined_content = f"[Relay from {request.sender}]: {request.content}"

    if request.trigger_evaluation:
        if request.agent_override:
            # Overriding the agent temporarily for this run
            session.model_config["agent_override"] = request.agent_override

        # Define a callback that routes back to the WebSocket manager
        async def send_to_ui(msg: dict[str, Any]) -> None:
            await ws_manager.send_to_session(session_id, msg)

        # Append execution to background tasks so we return 202 Accepted immediately
        def _run_in_background():
            import asyncio
            asyncio.create_task(run_conversation_turn(session, combined_content, send_to_ui))

        background_tasks.add_task(_run_in_background)

        return RelayTaskResponse(
            status="accepted",
            session_id=session_id,
            message="Task accepted and started processing.",
        )
    else:
        # Just broadcast that someone did something
        # Append to session history directly?
        return RelayTaskResponse(
            status="ignored",
            session_id=session_id,
            message="Evaluation omitted. Only broadcast supported.",
        )
