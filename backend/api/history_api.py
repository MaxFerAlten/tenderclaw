"""History API — manage past sessions, messages, and exports."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.history_service import session_history_service

logger = logging.getLogger("tenderclaw.api.history")
router = APIRouter(tags=["history"])


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    message_count: int
    model: str
    preview: str
    total_cost_usd: float


class SessionDetail(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    model: str
    message_count: int
    messages: list[dict]
    total_usage: dict
    total_cost_usd: float
    working_directory: str


class HistoryListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int


class HistoryPageResponse(BaseModel):
    entries: list[dict]
    total: int
    has_more: bool
    cursor: str | None


class MessagePageResponse(BaseModel):
    messages: list[dict]
    has_more: bool
    cursor: str | None


class DeleteResponse(BaseModel):
    status: str
    message: str


@router.get("", response_model=HistoryPageResponse)
async def get_sessions(
    limit: int = Query(20, ge=1, le=100),
    before_id: str | None = None,
    search: str | None = None,
) -> HistoryPageResponse:
    """Get paginated session history."""
    return session_history_service.get_sessions(
        limit=limit,
        before_id=before_id,
        search=search,
    )


@router.get("/legacy", response_model=HistoryListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> HistoryListResponse:
    """List past sessions with optional filtering (legacy)."""
    sessions = session_history_service.list_sessions(
        limit=limit,
        offset=offset,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )
    return HistoryListResponse(sessions=sessions, total=len(sessions))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """Get full session details including messages."""
    detail = session_history_service.get_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return SessionDetail(**detail)


@router.delete("/{session_id}", response_model=DeleteResponse)
async def delete_session(session_id: str) -> DeleteResponse:
    """Delete a session from history."""
    success = session_history_service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return DeleteResponse(status="ok", message=f"Session {session_id} deleted")


@router.get("/{session_id}/messages", response_model=MessagePageResponse)
async def get_session_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_id: str | None = None,
) -> MessagePageResponse:
    """Get paginated messages for a session."""
    result = session_history_service.get_session_messages_paginated(
        session_id,
        limit=limit,
        before_id=before_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return MessagePageResponse(**result)


@router.get("/{session_id}/messages/all")
async def get_session_messages_all(session_id: str) -> list[dict]:
    """Get all messages for a specific session (legacy)."""
    messages = session_history_service.get_session_messages(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return messages


@router.post("/export/{session_id}")
async def export_session(session_id: str) -> dict:
    """Export a session to JSON format."""
    export_data = session_history_service.export_session(session_id)
    if not export_data:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return export_data


@router.post("/import")
async def import_session(data: dict) -> dict:
    """Import a session from exported JSON."""
    session_id = session_history_service.import_session(data)
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session data")
    return {"status": "ok", "session_id": session_id}


@router.post("/export-all")
async def export_all_sessions() -> dict:
    """Export all sessions to JSON."""
    return session_history_service.export_all_sessions()
