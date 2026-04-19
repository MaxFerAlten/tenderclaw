"""Session store — in-memory session state management with disk persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.config import settings
from backend.schemas.messages import Message
from backend.schemas.sessions import SessionCreate, SessionStatus
from backend.services.chat_html import refresh_chat_entrypoints
from backend.services.workspace import (
    delete_session_artifacts,
    ensure_workspace_dirs,
    find_conversation_path,
    get_conversation_path,
    iter_conversation_paths,
)
from backend.utils.errors import SessionNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("tenderclaw.services.session_store")


def _get_state_dir() -> Path:
    """Return the session state directory.

    Uses a custom path from global config if set, otherwise falls back to
    the default ``~/workspace_tenderclaw/chat`` directory.
    """
    return ensure_workspace_dirs()


def _ensure_state_dir(dir_path: Path) -> None:
    """Create the state directory if it doesn't exist."""
    dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class SessionData:
    """Mutable session data for internal use."""
    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    model: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """Create SessionData from serialized disk data."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = datetime.now(UTC)
        else:
            created_at = datetime.now(UTC)
        messages = data.get("messages", []) if isinstance(data.get("messages"), list) else []
        reconstructed = []
        for m in messages:
            if isinstance(m, dict):
                try:
                    reconstructed.append(Message.model_validate(m))
                except Exception:
                    reconstructed.append(m)
            else:
                reconstructed.append(m)
        messages = reconstructed
        return cls(
            session_id=data.get("session_id", ""),
            status=SessionStatus(data.get("status", SessionStatus.IDLE.value)),
            model=data.get("model", ""),
            created_at=created_at,
            messages=messages,
            total_usage_input=data.get("total_usage_input", 0),
            total_usage_output=data.get("total_usage_output", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            working_directory=data.get("working_directory", "."),
            system_prompt_append=data.get("system_prompt_append", ""),
            should_abort=data.get("should_abort", False),
            model_config=data.get("model_config", {}),
            api_keys=data.get("api_keys", {}),
        )

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
        return entry.get("decision") if entry else None

    def clear_permission(self, tool_use_id: str) -> None:
        self._permission_events.pop(tool_use_id, None)


class SessionStore:
    """In-memory store for active sessions with optional disk persistence."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        ensure_workspace_dirs()

    def create(self, params: SessionCreate) -> SessionData:
        """Create a new session and return its state."""
        session_id = f"tc_{uuid.uuid4().hex[:12]}"
        state = SessionData(
            session_id=session_id,
            status=SessionStatus.IDLE,
            model=params.model or settings.default_model,
            created_at=datetime.now(UTC),
            working_directory=params.working_directory or ".",
            system_prompt_append=params.system_prompt_append or "",
        )
        # Apply global default permission mode so new sessions inherit it
        from backend.api.config import _global_config
        global_perm = _global_config.get("default_permission_mode")
        if global_perm:
            # Normalize to lowercase — PermissionMode enum uses lowercase values
            state.model_config["permission_mode"] = global_perm.lower()
        self._sessions[session_id] = state
        logger.info("Session created: %s (model=%s, permission_mode=%s)", session_id, state.model, state.model_config.get("permission_mode", "DEFAULT"))
        self._persist_session(state)
        return state

    def get(self, session_id: str) -> SessionData:
        """Get session state by ID. Raises SessionNotFoundError if missing."""
        state = self._sessions.get(session_id)
        if state is None:
            path = find_conversation_path(session_id)
            if path:
                try:
                    with open(path, encoding='utf-8') as f:
                        data = json.load(f)
                    state = SessionData.from_dict(data)
                    self._sessions[session_id] = state
                    logger.info("Session loaded from disk: %s", session_id)
                except Exception as exc:
                    logger.error("Failed to load session %s from disk: %s", session_id, exc)
                    raise SessionNotFoundError(f"Session not found: {session_id}")
            else:
                raise SessionNotFoundError(f"Session not found: {session_id}")
        # Apply global default if session has no permission_mode set
        if not state.model_config.get("permission_mode"):
            from backend.api.config import _global_config
            global_perm = _global_config.get("default_permission_mode")
            if global_perm:
                state.model_config["permission_mode"] = global_perm.lower()
        return state

    def list_sessions(self) -> list[SessionData]:
        return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
            delete_session_artifacts(session_id)
            refresh_chat_entrypoints()
            logger.info("Session deleted: %s", session_id)

    async def close_all(self) -> None:
        count = len(self._sessions)
        self._sessions.clear()
        logger.info("Closed %d sessions", count)

    def persist(self, state: SessionData) -> None:
        """Persist full session state including message history to disk.
        Called externally after conversation turns.
        """
        self._persist_session(state)

    def _persist_session(self, state: SessionData) -> None:
        """Persist full session snapshot including message history to disk."""
        try:
            _path = get_conversation_path(state.session_id, create_parent=True)
            serialized_messages = []
            for msg in state.messages:
                if hasattr(msg, "model_dump"):
                    serialized_messages.append(msg.model_dump())
                elif isinstance(msg, dict):
                    serialized_messages.append(msg)
                else:
                    serialized_messages.append({"role": str(msg.role), "content": str(msg.content), "message_id": getattr(msg, "message_id", "")})
            payload = {
                "session_id": state.session_id,
                "status": state.status.value if hasattr(state.status, "value") else str(state.status),
                "model": state.model,
                "created_at": state.created_at.isoformat() if hasattr(state, "created_at") else "",
                "updated_at": datetime.now(UTC).isoformat(),
                "messages": serialized_messages,
                "total_usage_input": state.total_usage_input,
                "total_usage_output": state.total_usage_output,
                "total_cost_usd": state.total_cost_usd,
                "working_directory": state.working_directory,
                "system_prompt_append": state.system_prompt_append,
                "should_abort": state.should_abort,
                "model_config": state.model_config,
                "api_keys": state.api_keys,
            }
            with open(_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            refresh_chat_entrypoints(state.session_id)
            logger.debug("Persisted session %s (%d messages) to disk at %s", state.session_id, len(state.messages), _path)
        except Exception as exc:
            logger.exception("Failed to persist session %s: %s", state.session_id, exc)

    def load_all_from_disk(self) -> None:
        """Load all persisted sessions from disk into memory (Wave 2 readiness)."""
        ensure_workspace_dirs()
        for f in iter_conversation_paths():
            try:
                with open(f, encoding='utf-8') as fh:
                    data = json.load(fh)
                sid = data.get("session_id") or f.stem
                if sid in self._sessions:
                    continue
                obj = SessionData.from_dict(data)
                self._sessions[sid] = obj
                logger.info("Loaded persisted session %s from disk", sid)
            except Exception as exc:
                logger.warning("Failed to load persisted session %s: %s", f, exc)


# Module-level instance
session_store = SessionStore()
