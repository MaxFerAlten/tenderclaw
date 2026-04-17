"""Session State Management — persistent session lifecycle with recovery.

Manages session persistence, resume, cost tracking, usage metrics, and
conversation history with disk-based checkpointing.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.schemas.sessions import SessionStatus
from backend.config import settings
from backend.utils.errors import SessionNotFoundError

logger = logging.getLogger("tenderclaw.runtime.session_state")

# Session persistence directory
SESSION_STATE_DIR = Path(".tenderclaw/sessions")
SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)

# Session timeout (24 hours)
SESSION_TIMEOUT_HOURS = 24


@dataclass
class UsageMetrics:
    """Token usage and cost tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0

    def add_usage(self, input_tokens: int, output_tokens: int, cost_per_1k_input: float, cost_per_1k_output: float) -> None:
        """Add token usage and calculate cost."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        input_cost = (input_tokens / 1000) * cost_per_1k_input
        output_cost = (output_tokens / 1000) * cost_per_1k_output
        self.total_cost_usd += input_cost + output_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class SessionState:
    """Persistent session state with full lifecycle management."""
    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    model: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    working_directory: str = "."
    messages: List[Dict[str, Any]] = field(default_factory=list)
    usage: UsageMetrics = field(default_factory=UsageMetrics)
    system_prompt_append: str = ""
    model_config: Dict[str, Any] = field(default_factory=dict)
    api_keys: Dict[str, str] = field(default_factory=dict)
    should_abort: bool = False
    is_expired: bool = False
    checkpoint_count: int = 0
    # Memory context injected at session start (not persisted across checkpoints)
    relevant_memory: str = ""
    # How many signals were auto-saved during this session
    signals_saved: int = 0
    # Serialized pending tool calls — survives checkpoints for reliable resume
    pending_tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def is_expired_session(self) -> bool:
        """Check if session has expired based on timeout."""
        if self.is_expired:
            return True
        
        expiry_time = self.last_activity + timedelta(hours=SESSION_TIMEOUT_HOURS)
        return datetime.now(UTC) > expiry_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        data['usage'] = self.usage.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create SessionState from dictionary."""
        # Convert ISO format strings back to datetime objects
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_activity' in data and isinstance(data['last_activity'], str):
            data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        
        # Handle usage metrics
        if 'usage' in data and isinstance(data['usage'], dict):
            usage_data = data['usage']
            data['usage'] = UsageMetrics(
                input_tokens=usage_data.get('input_tokens', 0),
                output_tokens=usage_data.get('output_tokens', 0),
                total_cost_usd=usage_data.get('total_cost_usd', 0.0)
            )
        
        return cls(**data)

    def save_to_disk(self) -> None:
        """Save session state to disk."""
        self.checkpoint_count += 1
        self.touch()
        
        file_path = SESSION_STATE_DIR / f"{self.session_id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.debug("Session %s saved to disk (checkpoint %d)", self.session_id, self.checkpoint_count)
        except Exception as e:
            logger.error("Failed to save session %s to disk: %s", self.session_id, e)
            raise

    @classmethod
    def load_from_disk(cls, session_id: str) -> 'SessionState':
        """Load session state from disk."""
        file_path = SESSION_STATE_DIR / f"{session_id}.json"
        if not file_path.exists():
            raise SessionNotFoundError(f"Session not found: {session_id}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            session = cls.from_dict(data)
            logger.debug("Session %s loaded from disk", session_id)
            return session
        except Exception as e:
            logger.error("Failed to load session %s from disk: %s", session_id, e)
            raise SessionNotFoundError(f"Failed to load session: {e}")

    @classmethod
    def list_sessions(cls) -> List[str]:
        """List all persisted session IDs."""
        if not SESSION_STATE_DIR.exists():
            return []
        
        session_files = SESSION_STATE_DIR.glob("*.json")
        return [f.stem for f in session_files if f.is_file()]

    @classmethod
    def delete_from_disk(cls, session_id: str) -> None:
        """Delete session state from disk."""
        file_path = SESSION_STATE_DIR / f"{session_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug("Session %s deleted from disk", session_id)
        except Exception as e:
            logger.error("Failed to delete session %s from disk: %s", session_id, e)
            raise

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """Clean up expired sessions from disk. Returns count of removed sessions."""
        removed_count = 0
        for session_id in cls.list_sessions():
            try:
                session = cls.load_from_disk(session_id)
                if session.is_expired_session():
                    cls.delete_from_disk(session_id)
                    removed_count += 1
                    logger.info("Removed expired session: %s", session_id)
            except SessionNotFoundError:
                # Session was already deleted
                pass
            except Exception as e:
                logger.error("Error checking session %s for expiry: %s", session_id, e)

        return removed_count

    # ------------------------------------------------------------------
    # Tool lifecycle tracking (Sprint 2)
    # ------------------------------------------------------------------

    def record_tool_state(
        self,
        tool_use_id: str,
        tool_name: str,
        state: str,
        tool_input: Optional[Dict[str, Any]] = None,
        result_preview: str = "",
        is_error: bool = False,
    ) -> None:
        """Create or update the state record for a tool call.

        Keeps only the last entry for each tool_use_id. Entries for
        COMPLETED/FAILED/DENIED are retained in the list so resume can
        reconstruct what happened; entries older than the last 50 are dropped.
        """
        from backend.schemas.permissions import ToolCallState

        now = datetime.now(UTC).isoformat()
        # Find existing record
        for record in self.pending_tool_calls:
            if record.get("tool_use_id") == tool_use_id:
                record["state"] = state
                if result_preview:
                    record["result_preview"] = result_preview[:200]
                record["is_error"] = is_error
                if state in (
                    ToolCallState.COMPLETED.value,
                    ToolCallState.FAILED.value,
                    ToolCallState.DENIED.value,
                ):
                    record["resolved_at"] = now
                return

        # New record
        entry: Dict[str, Any] = {
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "state": state,
            "input": tool_input or {},
            "result_preview": result_preview[:200] if result_preview else "",
            "is_error": is_error,
            "created_at": now,
            "resolved_at": None,
        }
        self.pending_tool_calls.append(entry)
        # Keep bounded — drop resolved entries beyond 50
        if len(self.pending_tool_calls) > 50:
            from backend.schemas.permissions import ToolCallState
            resolved_states = {
                ToolCallState.COMPLETED.value,
                ToolCallState.FAILED.value,
                ToolCallState.DENIED.value,
            }
            unresolved = [r for r in self.pending_tool_calls if r["state"] not in resolved_states]
            resolved = [r for r in self.pending_tool_calls if r["state"] in resolved_states]
            self.pending_tool_calls = unresolved + resolved[-50:]

    def get_unresolved_tool_calls(self) -> List[Dict[str, Any]]:
        """Return tool calls still in REQUESTED, APPROVED, or RUNNING state."""
        from backend.schemas.permissions import ToolCallState
        unresolved = {
            ToolCallState.REQUESTED.value,
            ToolCallState.APPROVED.value,
            ToolCallState.RUNNING.value,
        }
        return [r for r in self.pending_tool_calls if r["state"] in unresolved]

    def load_memory_context(self, project_root: str = ".") -> None:
        """Load relevant memory at session start and store in relevant_memory.

        Called once during session initialization. Builds a prompt-ready block
        from USER + REPO + TEAM scopes so it can be prepended to the system prompt.
        """
        try:
            from backend.memory.memory_manager import memory_manager
            from backend.memory.memory_types import MemoryScope
            # Use the first few existing messages (if resuming) or an empty list
            context_block = memory_manager.build_context_for_prompt(
                self.messages[-4:] if self.messages else [],
                project_root=project_root,
                scopes=[MemoryScope.USER, MemoryScope.REPO, MemoryScope.TEAM],
            )
            self.relevant_memory = context_block
            logger.info(
                "Session %s loaded memory context (%d chars)",
                self.session_id,
                len(context_block),
            )
        except Exception as exc:
            logger.warning("Failed to load memory context for session %s: %s", self.session_id, exc)
            self.relevant_memory = ""

    def trigger_memory_scan(self, project_root: str = ".") -> int:
        """Extract memory signals from conversation and auto-save them.

        Called at the end of each turn. Returns number of signals saved.
        """
        if not self.messages:
            return 0
        try:
            from backend.memory.memory_scan import extract_signals_from_transcript
            from backend.memory.memory_manager import memory_manager
            signals = extract_signals_from_transcript(self.messages, session_id=self.session_id)
            saved = memory_manager.auto_save_signals(signals, project_root=project_root)
            self.signals_saved += saved
            logger.info(
                "Session %s end-of-turn scan: %d signals saved (total: %d)",
                self.session_id,
                saved,
                self.signals_saved,
            )
            return saved
        except Exception as exc:
            logger.warning("Memory scan failed for session %s: %s", self.session_id, exc)
            return 0