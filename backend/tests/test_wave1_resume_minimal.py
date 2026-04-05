from __future__ import annotations

import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.schemas.sessions import SessionCreate
from backend.services.session_store import session_store


def test_wave1_resume_minimal_roundtrip():
    # Create a session and ensure it persists to disk
    state = session_store.create(SessionCreate(model=None, system_prompt_append=None, working_directory='.'))
    sid = state.session_id
    # Ensure we can load it via get() even if not in memory
    if sid in session_store._sessions:
        del session_store._sessions[sid]
    loaded = session_store.get(sid)
    assert loaded.session_id == sid
    assert loaded.model == (state.model or '')
