from __future__ import annotations

import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.schemas.sessions import SessionCreate
from backend.services.session_store import session_store


def test_wave1_resume_minimal_roundtrip():
    state = session_store.create(SessionCreate(model=None, system_prompt_append=None, working_directory='.'))
    sid = state.session_id
    if sid in session_store._sessions:
        del session_store._sessions[sid]
    loaded = session_store.get(sid)
    assert loaded.session_id == sid
    assert loaded.model == (state.model or '')


def test_wave1_message_persistence_roundtrip():
    from backend.schemas.messages import Message, Role
    state = session_store.create(SessionCreate(model=None, system_prompt_append=None, working_directory='.'))
    sid = state.session_id
    state.messages.append(Message(role=Role.USER, content="Hello", message_id="msg_001"))
    state.messages.append(Message(role=Role.ASSISTANT, content="Hi there!", message_id="msg_002"))
    state.total_usage_input = 10
    state.total_usage_output = 20
    session_store.persist(state)
    if sid in session_store._sessions:
        del session_store._sessions[sid]
    loaded = session_store.get(sid)
    assert len(loaded.messages) == 2
    assert loaded.messages[0].role == Role.USER
    assert loaded.messages[1].role == Role.ASSISTANT
    assert loaded.total_usage_input == 10
    assert loaded.total_usage_output == 20
