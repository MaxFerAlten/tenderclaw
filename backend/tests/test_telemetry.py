from backend.schemas.sessions import SessionStatus
from backend.services.session_store import SessionData
from backend.telemetry.metrics import (
    _active_sessions_count,
    _observe_active_sessions,
    _observe_queue_depth,
    _queue_depth_count,
)


def test_active_sessions_count_uses_live_store(monkeypatch):
    sessions = {
        "tc_1": SessionData(session_id="tc_1", status=SessionStatus.IDLE),
        "tc_2": SessionData(session_id="tc_2", status=SessionStatus.BUSY),
        "tc_3": SessionData(session_id="tc_3", status=SessionStatus.ACTIVE),
    }

    class StubStore:
        def list_sessions(self):
            return list(sessions.values())

    monkeypatch.setattr("backend.telemetry.metrics.session_store", StubStore())

    assert _active_sessions_count() == 3
    assert _queue_depth_count() == 1


def test_observable_callbacks_return_observations(monkeypatch):
    sessions = [
        SessionData(session_id="tc_1", status=SessionStatus.BUSY),
        SessionData(session_id="tc_2", status=SessionStatus.BUSY),
    ]

    class StubStore:
        def list_sessions(self):
            return sessions

    monkeypatch.setattr("backend.telemetry.metrics.session_store", StubStore())

    active = _observe_active_sessions(None)
    queue_depth = _observe_queue_depth(None)

    assert len(active) == 1
    assert active[0].value == 2
    assert len(queue_depth) == 1
    assert queue_depth[0].value == 2
