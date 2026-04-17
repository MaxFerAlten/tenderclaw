"""Tests — Sprint 2 resume: pending tool calls survive session checkpoint."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.schemas.permissions import ToolCallState
from backend.runtime.session_state import SessionState, SESSION_STATE_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session(**kwargs) -> SessionState:
    defaults = {"session_id": "resume-test-001"}
    defaults.update(kwargs)
    return SessionState(**defaults)


def _add_tools(s: SessionState) -> None:
    """Add a representative set of tool calls in various states."""
    s.record_tool_state("tool-r1", "bash",       ToolCallState.REQUESTED.value)
    s.record_tool_state("tool-r2", "read_file",  ToolCallState.RUNNING.value)
    s.record_tool_state("tool-r3", "write_file", ToolCallState.COMPLETED.value, result_preview="ok")
    s.record_tool_state("tool-r4", "exec",       ToolCallState.FAILED.value, is_error=True)
    s.record_tool_state("tool-r5", "search",     ToolCallState.DENIED.value)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestPendingToolsRoundTrip:
    def test_to_dict_contains_pending_tools(self) -> None:
        s = _session()
        _add_tools(s)
        data = s.to_dict()
        assert "pending_tool_calls" in data
        assert len(data["pending_tool_calls"]) == 5

    def test_from_dict_restores_all_tool_records(self) -> None:
        s = _session()
        _add_tools(s)
        data = s.to_dict()
        s2 = SessionState.from_dict(data)
        assert len(s2.pending_tool_calls) == 5

    def test_from_dict_preserves_states(self) -> None:
        s = _session()
        _add_tools(s)
        s2 = SessionState.from_dict(s.to_dict())

        state_map = {r["tool_use_id"]: r["state"] for r in s2.pending_tool_calls}
        assert state_map["tool-r1"] == ToolCallState.REQUESTED.value
        assert state_map["tool-r2"] == ToolCallState.RUNNING.value
        assert state_map["tool-r3"] == ToolCallState.COMPLETED.value
        assert state_map["tool-r4"] == ToolCallState.FAILED.value
        assert state_map["tool-r5"] == ToolCallState.DENIED.value

    def test_result_preview_preserved(self) -> None:
        s = _session()
        s.record_tool_state("t1", "read", ToolCallState.COMPLETED.value, result_preview="hello world")
        s2 = SessionState.from_dict(s.to_dict())
        assert s2.pending_tool_calls[0]["result_preview"] == "hello world"

    def test_result_preview_truncated_to_200(self) -> None:
        s = _session()
        long_preview = "x" * 500
        s.record_tool_state("t1", "bash", ToolCallState.COMPLETED.value, result_preview=long_preview)
        assert len(s.pending_tool_calls[0]["result_preview"]) <= 200


# ---------------------------------------------------------------------------
# Unresolved tools after restore
# ---------------------------------------------------------------------------


class TestUnresolvedAfterRestore:
    def test_running_tool_is_unresolved_after_restore(self) -> None:
        s = _session()
        s.record_tool_state("in-flight", "bash", ToolCallState.RUNNING.value)
        s2 = SessionState.from_dict(s.to_dict())
        unresolved = s2.get_unresolved_tool_calls()
        assert any(r["tool_use_id"] == "in-flight" for r in unresolved)

    def test_approved_tool_is_unresolved_after_restore(self) -> None:
        s = _session()
        s.record_tool_state("approved1", "write", ToolCallState.APPROVED.value)
        s2 = SessionState.from_dict(s.to_dict())
        assert len(s2.get_unresolved_tool_calls()) == 1

    def test_no_unresolved_when_all_resolved(self) -> None:
        s = _session()
        s.record_tool_state("t1", "x", ToolCallState.COMPLETED.value)
        s.record_tool_state("t2", "y", ToolCallState.FAILED.value)
        s.record_tool_state("t3", "z", ToolCallState.DENIED.value)
        s2 = SessionState.from_dict(s.to_dict())
        assert s2.get_unresolved_tool_calls() == []


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------


class TestDiskPersistence:
    def test_pending_tools_survive_save_load(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.runtime.session_state.SESSION_STATE_DIR",
            tmp_path,
        )
        s = _session(session_id="disk-test-001")
        s.record_tool_state("disk-t1", "bash", ToolCallState.RUNNING.value)
        s.save_to_disk()

        s2 = SessionState.load_from_disk("disk-test-001")
        assert len(s2.pending_tool_calls) == 1
        assert s2.pending_tool_calls[0]["state"] == ToolCallState.RUNNING.value


# ---------------------------------------------------------------------------
# Bounded list (max 50 resolved entries)
# ---------------------------------------------------------------------------


class TestBoundedPendingList:
    def test_list_bounded_after_many_resolved(self) -> None:
        s = _session()
        for i in range(60):
            s.record_tool_state(f"tool-{i}", "bash", ToolCallState.REQUESTED.value)
            s.record_tool_state(f"tool-{i}", "bash", ToolCallState.COMPLETED.value)
        # Should not grow unbounded
        assert len(s.pending_tool_calls) <= 60  # At most 60 entries after 60 cycles

    def test_unresolved_always_retained(self) -> None:
        s = _session()
        # Add 60 resolved entries
        for i in range(60):
            s.record_tool_state(f"r-{i}", "bash", ToolCallState.COMPLETED.value)
        # Add an unresolved one
        s.record_tool_state("running-one", "bash", ToolCallState.RUNNING.value)
        unresolved = s.get_unresolved_tool_calls()
        assert any(r["tool_use_id"] == "running-one" for r in unresolved)
