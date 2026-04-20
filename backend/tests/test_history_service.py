from __future__ import annotations

import json

from backend.services import history_service as history_module


def test_list_sessions_applies_date_filters_with_timezone_aware_timestamps(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    history_dir = tmp_path / "history"
    state_dir.mkdir()
    history_dir.mkdir()

    monkeypatch.setattr(history_module, "STATE_DIR", state_dir)
    monkeypatch.setattr(history_module, "HISTORY_DIR", history_dir)

    service = history_module.SessionHistoryService()

    sessions = {
        "tc_old": "2026-04-17T23:30:00+00:00",
        "tc_match": "2026-04-18T12:00:00+00:00",
        "tc_new": "2026-04-19T08:15:00+00:00",
    }
    for session_id, created_at in sessions.items():
        payload = {
            "session_id": session_id,
            "created_at": created_at,
            "messages": [{"role": "user", "content": session_id}],
            "model": "claude-sonnet",
        }
        (state_dir / f"{session_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    results = service.list_sessions(date_from="2026-04-18", date_to="2026-04-18")

    assert [item["session_id"] for item in results] == ["tc_match"]


def test_delete_all_sessions_removes_every_saved_session(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    history_dir = tmp_path / "history"
    state_dir.mkdir()
    history_dir.mkdir()

    monkeypatch.setattr(history_module, "STATE_DIR", state_dir)
    monkeypatch.setattr(history_module, "HISTORY_DIR", history_dir)

    service = history_module.SessionHistoryService()

    for session_id in ("tc_one", "tc_two"):
        payload = {
            "session_id": session_id,
            "created_at": "2026-04-20T10:00:00+00:00",
            "messages": [{"role": "user", "content": session_id}],
            "model": "claude-sonnet",
        }
        (state_dir / f"{session_id}.json").write_text(json.dumps(payload), encoding="utf-8")
        (history_dir / f"{session_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    deleted_count = service.delete_all_sessions()

    assert deleted_count == 2
    assert service.list_sessions() == []
    assert list(state_dir.glob("*.json")) == []
    assert list(history_dir.glob("*.json")) == []
