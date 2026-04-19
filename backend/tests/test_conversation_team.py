from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.schemas.messages import Message, Role
from backend.services.session_store import SessionData


@pytest.mark.asyncio
async def test_explicit_team_command_is_persisted_before_pipeline(monkeypatch):
    from backend.core import conversation

    session = SessionData(
        session_id="tc_team_1",
        model="claude-sonnet",
        messages=[
            Message(role=Role.USER, content="previous question", message_id="msg_prev_user"),
            Message(role=Role.ASSISTANT, content="previous answer", message_id="msg_prev_assistant"),
        ],
    )
    dispatch = AsyncMock()
    validate = AsyncMock(return_value=True)
    captured: dict[str, object] = {}

    async def fake_run_team_pipeline(session_arg: SessionData, task: str, send) -> None:
        captured["task"] = task
        captured["history"] = conversation._to_api_messages(session_arg.messages[:-1])

    monkeypatch.setattr(conversation.hook_dispatcher, "dispatch", dispatch)
    monkeypatch.setattr(conversation, "_validate_api_key", validate)
    monkeypatch.setattr(conversation, "_run_team_pipeline", fake_run_team_pipeline)

    await conversation._run_conversation_turn_impl(session, "/team implement the fix", AsyncMock())

    assert session.messages[-1].content == "/team implement the fix"
    assert captured["task"] == "implement the fix"
    assert captured["history"] == [
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
    ]
    validate.assert_awaited_once()
    assert dispatch.await_count >= 2
