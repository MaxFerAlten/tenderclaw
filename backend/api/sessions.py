"""Session CRUD endpoints — /api/sessions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from backend.schemas.sessions import SessionCreate, SessionInfo
from backend.services.session_store import session_store
from backend.utils.errors import SessionNotFoundError
from fastapi import HTTPException

logger = logging.getLogger("tenderclaw.api.sessions")
router = APIRouter()


@router.post("", response_model=SessionInfo, status_code=201)
async def create_session(body: SessionCreate) -> SessionInfo:
    """Create a new session and return its metadata."""
    state = session_store.create(body)
    logger.info("Created session %s", state.session_id)
    return state.to_info()


@router.get("", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    """List all active sessions."""
    states = session_store.list_sessions()
    return [s.to_info() for s in states]


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """Get metadata for a single session."""
    try:
        state = session_store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return state.to_info()


@router.get("/{session_id}/resume", response_model=SessionInfo)
async def resume_session(session_id: str) -> SessionInfo:
    """Resume a session by ensuring its state is loaded (Wave 2 readiness)."""
    try:
        state = session_store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return state.to_info()


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> Response:
    """Delete a session."""
    try:
        session_store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    session_store.delete(session_id)
    logger.info("Deleted session %s", session_id)
    return Response(status_code=204)
