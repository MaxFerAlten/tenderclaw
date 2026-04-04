"""Wave 1 Smoke Test (robust install path).

This script exercises basic Wave 1 primitives: session creation, adding a user
message, and building the system prompt. It prints a compact summary to stdout
so it can be used as a quick verifiability smoke-test in CI or manual runs.
"""

from __future__ import annotations

import sys
sys.path.append('D:/MY_AI/claude-code/TenderClaw')

from backend.schemas.sessions import SessionCreate
from backend.services.session_store import session_store
from backend.schemas.messages import Message, Role
from backend.core.system_prompt import build_system_prompt


def run():
    # Create a new session
    state = session_store.create(SessionCreate(model=None, system_prompt_append=None, working_directory="."))
    sid = state.session_id
    print(f"session_id={sid}")

    # Push a user message
    state.messages.append(Message(role=Role.USER, content="hello wave1"))

    # Build system prompt
    system = build_system_prompt(working_directory=state.working_directory, append=state.system_prompt_append)
    print("SYSTEM_PROMPT_START")
    print(system[:2000] + ("..." if len(system) > 2000 else ""))
    print("SYSTEM_PROMPT_END")

    # Print messages
    print("MESSAGES:")
    for i, m in enumerate(state.messages, 1):
        c = m.content if isinstance(m.content, str) else "<block>"
        print(f"{i}: {m.role.value} -> {c}")

    # Quick persistence check (Wave 1) - verify state dir exists and a snapshot was created
    import os
    state_dir = os.path.join('.tenderclaw', 'state')
    print("STATE_DIR_EXISTS:", os.path.isdir(state_dir))
    if os.path.isdir(state_dir):
        try:
            files = os.listdir(state_dir)
            print("STATE_SNAPSHOT_FILES:", files)
        except Exception as e:
            print("STATE_SNAPSHOT_READ_ERROR:", e)


if __name__ == '__main__':
    run()
