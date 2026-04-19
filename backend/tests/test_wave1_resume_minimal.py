from __future__ import annotations

import pytest

from backend.api import config as config_module
from backend.schemas.sessions import SessionCreate
from backend.services.session_store import session_store


@pytest.fixture(autouse=True)
def isolated_chat_storage(tmp_path):
    config_snapshot = dict(config_module._global_config)
    session_snapshot = dict(session_store._sessions)
    config_module._global_config["chat_storage_path"] = str(tmp_path / "chat")
    try:
        yield
    finally:
        config_module._global_config.clear()
        config_module._global_config.update(config_snapshot)
        session_store._sessions.clear()
        session_store._sessions.update(session_snapshot)


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
