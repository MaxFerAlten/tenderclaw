"""Session store — in-memory session state management.

Persistence to disk (.tenderclaw/) will be added in Phase 2.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from backend.schemas.sessions import SessionCreate, SessionState, SessionStatus
from backend.config import settings
from backend.utils.errors import SessionNotFoundError

logger = logging.getLogger("tenderclaw.services.session_store")


class SessionStore:
    """In-memory store for active sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, params: SessionCreate) -> SessionState:
        """Create a new session and return its state."""
        session_id = f"tc_{uuid.uuid4().hex[:12]}"
        state = SessionState(
            session_id=session_id,
            status=SessionStatus.IDLE,
            model=params.model or settings.default_model,
            created_at=datetime.utcnow(),
            working_directory=params.working_directory or ".",
            system_prompt_append=params.system_prompt_append or "",
        )
        self._sessions[session_id] = state
        logger.info("Session created: %s (model=%s)", session_id, state.model)
        return state

    def get(self, session_id: str) -> SessionState:
        """Get session state by ID. Raises SessionNotFoundError if missing."""
        state = self._sessions.get(session_id)
        if state is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return state

    def list_sessions(self) -> list[SessionState]:
        """List all active sessions."""
        return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session deleted: %s", session_id)

    async def close_all(self) -> None:
        """Close all sessions (called on shutdown)."""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info("Closed %d sessions", count)


# Module-level instance
session_store = SessionStore()
