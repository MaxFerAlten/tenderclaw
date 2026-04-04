"""Session store — in-memory session state management with disk persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

from backend.schemas.sessions import SessionCreate, SessionStatus
from backend.config import settings
from backend.utils.errors import SessionNotFoundError

logger = logging.getLogger("tenderclaw.services.session_store")

STATE_DIR = Path(".tenderclaw/state")


@dataclass
class SessionData:
    """Mutable session data for internal use."""
    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    model: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    messages: list = field(default_factory=list)
    total_usage_input: int = 0
    total_usage_output: int = 0
    total_cost_usd: float = 0.0
    working_directory: str = "."
    system_prompt_append: str = ""
    should_abort: bool = False
    model_config: dict = field(default_factory=dict)
    # Per-session API keys (override global settings)
    api_keys: dict[str, str] = field(default_factory=dict)
    # Permission queue: tool_use_id -> asyncio.Event + decision
    _permission_events: dict = field(default_factory=dict, repr=False)

    def to_info(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "model": self.model,
            "created_at": self.created_at,
            "message_count": len(self.messages),
            "total_usage": {"input_tokens": self.total_usage_input, "output_tokens": self.total_usage_output},
            "total_cost_usd": self.total_cost_usd,
        }

    def set_api_key(self, provider: str, key: str) -> None:
        self.api_keys[provider] = key

    def get_api_key(self, provider: str) -> str | None:
        return self.api_keys.get(provider) or None

    # --- Permission gate helpers ---

    def register_permission_request(self, tool_use_id: str) -> asyncio.Event:
        """Register a pending permission request; returns an Event to await."""
        event = asyncio.Event()
        self._permission_events[tool_use_id] = {"event": event, "decision": None}
        return event

    def resolve_permission(self, tool_use_id: str, decision: str) -> None:
        """Resolve a pending permission request with approve/deny."""
        entry = self._permission_events.get(tool_use_id)
        if entry:
            entry["decision"] = decision
            entry["event"].set()

    def get_permission_decision(self, tool_use_id: str) -> str | None:
        """Get the resolved decision for a tool_use_id."""
        entry = self._permission_events.get(tool_use_id)
        return entry["decision"] if entry else None

    def clear_permission(self, tool_use_id: str) -> None:
        self._permission_events.pop(tool_use_id, None)


class SessionStore:
    """In-memory store for active sessions with optional disk persistence."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    def create(self, params: SessionCreate) -> SessionData:
        """Create a new session and return its state."""
        session_id = f"tc_{uuid.uuid4().hex[:12]}"
        state = SessionData(
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

    def get(self, session_id: str) -> SessionData:
        """Get session state by ID. Raises SessionNotFoundError if missing."""
        state = self._sessions.get(session_id)
        if state is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return state

    def list_sessions(self) -> list[SessionData]:
        return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
            _path = STATE_DIR / f"{session_id}.json"
            _path.unlink(missing_ok=True)
            logger.info("Session deleted: %s", session_id)

    async def close_all(self) -> None:
        count = len(self._sessions)
        self._sessions.clear()
        logger.info("Closed %d sessions", count)


# Module-level instance
session_store = SessionStore()
