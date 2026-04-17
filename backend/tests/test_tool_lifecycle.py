"""Tests — Sprint 2 tool lifecycle: state machine transitions on SessionState."""

from __future__ import annotations

import pytest

from backend.schemas.permissions import ToolCallState
from backend.runtime.session_state import SessionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(session_id: str = "test-session-001") -> SessionState:
    return SessionState(session_id=session_id)


def _transition(session: SessionState, tool_id: str, tool_name: str, state: ToolCallState, **kwargs) -> None:
    session.record_tool_state(
        tool_use_id=tool_id,
        tool_name=tool_name,
        state=state.value,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_no_pending_tools_on_new_session(self) -> None:
        s = _make_session()
        assert s.pending_tool_calls == []

    def test_get_unresolved_empty_for_new_session(self) -> None:
        s = _make_session()
        assert s.get_unresolved_tool_calls() == []


# ---------------------------------------------------------------------------
# State machine: create
# ---------------------------------------------------------------------------


class TestRecordToolState:
    def test_requested_creates_record(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.REQUESTED)
        assert len(s.pending_tool_calls) == 1
        assert s.pending_tool_calls[0]["state"] == ToolCallState.REQUESTED.value
        assert s.pending_tool_calls[0]["tool_name"] == "bash"

    def test_transition_updates_existing_record(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.REQUESTED)
        _transition(s, "id1", "bash", ToolCallState.APPROVED)
        assert len(s.pending_tool_calls) == 1
        assert s.pending_tool_calls[0]["state"] == ToolCallState.APPROVED.value

    def test_full_happy_path(self) -> None:
        s = _make_session()
        _transition(s, "id1", "read_file", ToolCallState.REQUESTED)
        _transition(s, "id1", "read_file", ToolCallState.APPROVED)
        _transition(s, "id1", "read_file", ToolCallState.RUNNING)
        _transition(s, "id1", "read_file", ToolCallState.COMPLETED, result_preview="file contents")
        assert s.pending_tool_calls[0]["state"] == ToolCallState.COMPLETED.value
        assert "file contents" in s.pending_tool_calls[0]["result_preview"]

    def test_denied_path(self) -> None:
        s = _make_session()
        _transition(s, "id2", "delete_file", ToolCallState.REQUESTED)
        _transition(s, "id2", "delete_file", ToolCallState.DENIED)
        assert s.pending_tool_calls[0]["state"] == ToolCallState.DENIED.value

    def test_failed_path(self) -> None:
        s = _make_session()
        _transition(s, "id3", "bash", ToolCallState.REQUESTED)
        _transition(s, "id3", "bash", ToolCallState.APPROVED)
        _transition(s, "id3", "bash", ToolCallState.RUNNING)
        _transition(s, "id3", "bash", ToolCallState.FAILED, is_error=True)
        assert s.pending_tool_calls[0]["state"] == ToolCallState.FAILED.value
        assert s.pending_tool_calls[0]["is_error"] is True

    def test_multiple_tools_tracked_independently(self) -> None:
        s = _make_session()
        _transition(s, "id1", "read", ToolCallState.REQUESTED)
        _transition(s, "id2", "write", ToolCallState.REQUESTED)
        _transition(s, "id1", "read", ToolCallState.COMPLETED)
        assert len(s.pending_tool_calls) == 2
        states = {r["tool_use_id"]: r["state"] for r in s.pending_tool_calls}
        assert states["id1"] == ToolCallState.COMPLETED.value
        assert states["id2"] == ToolCallState.REQUESTED.value


# ---------------------------------------------------------------------------
# get_unresolved_tool_calls
# ---------------------------------------------------------------------------


class TestGetUnresolvedToolCalls:
    def test_requested_is_unresolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.REQUESTED)
        assert len(s.get_unresolved_tool_calls()) == 1

    def test_approved_is_unresolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.APPROVED)
        assert len(s.get_unresolved_tool_calls()) == 1

    def test_running_is_unresolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.RUNNING)
        assert len(s.get_unresolved_tool_calls()) == 1

    def test_completed_is_resolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.COMPLETED)
        assert s.get_unresolved_tool_calls() == []

    def test_denied_is_resolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.DENIED)
        assert s.get_unresolved_tool_calls() == []

    def test_failed_is_resolved(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.FAILED)
        assert s.get_unresolved_tool_calls() == []

    def test_mixed_unresolved_count(self) -> None:
        s = _make_session()
        _transition(s, "id1", "read", ToolCallState.RUNNING)
        _transition(s, "id2", "write", ToolCallState.COMPLETED)
        _transition(s, "id3", "exec", ToolCallState.REQUESTED)
        unresolved = s.get_unresolved_tool_calls()
        assert len(unresolved) == 2
        ids = {r["tool_use_id"] for r in unresolved}
        assert "id1" in ids and "id3" in ids


# ---------------------------------------------------------------------------
# Serialization (via to_dict / from_dict)
# ---------------------------------------------------------------------------


class TestPendingToolsSerialization:
    def test_pending_tools_survive_serialization(self) -> None:
        s = _make_session()
        _transition(s, "id1", "bash", ToolCallState.RUNNING)
        _transition(s, "id2", "read", ToolCallState.COMPLETED, result_preview="contents")

        data = s.to_dict()
        assert "pending_tool_calls" in data
        assert len(data["pending_tool_calls"]) == 2

        s2 = SessionState.from_dict(data)
        assert len(s2.pending_tool_calls) == 2
        running = [r for r in s2.pending_tool_calls if r["tool_use_id"] == "id1"]
        assert running[0]["state"] == ToolCallState.RUNNING.value

    def test_unresolved_tools_flagged_after_restore(self) -> None:
        s = _make_session()
        _transition(s, "pending1", "write", ToolCallState.APPROVED)
        data = s.to_dict()
        s2 = SessionState.from_dict(data)
        unresolved = s2.get_unresolved_tool_calls()
        assert any(r["tool_use_id"] == "pending1" for r in unresolved)
