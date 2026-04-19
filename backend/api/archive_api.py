"""Archive API — manage archived sessions and images in workspace."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.image_store import get_session_images as _get_image_files
from backend.services.session_archiver import (
    delete_archived_session,
    get_archived_session,
    list_archived_sessions,
)

logger = logging.getLogger("tenderclaw.api.archive")
router = APIRouter(tags=["archive"])


class ArchivedSessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    message_count: int
    model: str
    total_cost_usd: float
    status: str | None = None


class ArchivedSessionDetail(ArchivedSessionSummary):
    messages: list[dict]
    updated_at: str


class ImageInfo(BaseModel):
    name: str
    path: str
    size_bytes: int


@router.get("/sessions", response_model=list[ArchivedSessionSummary])
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
) -> list[ArchivedSessionSummary]:
    """List all archived sessions from workspace."""
    sessions = list_archived_sessions()
    if search:
        kw = search.lower()
        sessions = [s for s in sessions if kw in s.get("title", "").lower()]
    return sessions[:limit]


@router.get("/sessions/{session_id}", response_model=ArchivedSessionDetail)
async def get_session(session_id: str) -> ArchivedSessionDetail:
    """Get full archived session details."""
    data = get_archived_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Archived session not found: {session_id}")

    messages = data.get("messages", [])
    return ArchivedSessionDetail(
        session_id=data.get("session_id", session_id),
        title=_extract_title(data),
        created_at=data.get("created_at", ""),
        message_count=len(messages),
        model=data.get("model", ""),
        total_cost_usd=data.get("total_cost_usd", 0.0),
        status=data.get("status"),
        messages=messages,
        updated_at=data.get("updated_at", data.get("created_at", "")),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete an archived session and all its files."""
    if not delete_archived_session(session_id):
        raise HTTPException(status_code=404, detail=f"Archived session not found: {session_id}")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/images", response_model=list[ImageInfo])
async def get_images(session_id: str) -> list[ImageInfo]:
    """List all images for an archived session."""
    return _get_image_files(session_id)


def _extract_title(data: dict) -> str:
    messages = data.get("messages", [])
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:80] + ("..." if len(content) > 80 else "")
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")[:80]
                        return text + ("..." if len(text) == 80 else "")
    return "Untitled Session"
