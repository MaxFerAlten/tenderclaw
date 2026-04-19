from __future__ import annotations

import pytest

from backend.services.providers.lmstudio_provider import LMStudioProvider, _to_openai_messages


class _Delta:
    def __init__(
        self,
        content: str = "",
        reasoning_content: str | None = None,
        tool_calls: list[object] | None = None,
    ) -> None:
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


class _FunctionDelta:
    def __init__(self, name: str | None = None, arguments: str | None = None) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCallDelta:
    def __init__(
        self,
        *,
        index: int | None = 0,
        id: str | None = None,
        name: str | None = None,
        arguments: str | None = None,
    ) -> None:
        self.index = index
        self.id = id
        self.function = _FunctionDelta(name=name, arguments=arguments)


class _Choice:
    def __init__(self, delta: _Delta, finish_reason: str | None = None) -> None:
        self.delta = delta
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, choice: _Choice) -> None:
        self.choices = [choice]


class _FakeStream:
    def __init__(self, chunks: list[_Chunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _FakeStream:
        self._index = 0
        return self

    async def __anext__(self) -> _Chunk:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class _FakeCompletions:
    def __init__(self, stream: _FakeStream) -> None:
        self._stream = stream
        self.calls: list[dict[str, object]] = []

    async def create(self, **_kwargs: object) -> _FakeStream:
        self.calls.append(_kwargs)
        return self._stream


class _FakeChat:
    def __init__(self, stream: _FakeStream) -> None:
        self.completions = _FakeCompletions(stream)


class _FakeClient:
    def __init__(self, stream: _FakeStream) -> None:
        self.chat = _FakeChat(stream)


def test_lmstudio_assistant_history_uses_string_content_for_tool_calls() -> None:
    messages = _to_openai_messages(
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Controllo il file."},
                    {"type": "tool_use", "id": "call_1", "name": "Read", "input": {"file_path": "a.py"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": "ok", "is_error": False},
                ],
            },
        ]
    )

    assert messages == [
        {
            "role": "assistant",
            "content": "Controllo il file.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "Read", "arguments": '{"file_path": "a.py"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
    ]


@pytest.mark.asyncio
async def test_lmstudio_reasoning_content_is_not_visible_text() -> None:
    stream = _FakeStream(
        [
            _Chunk(_Choice(_Delta(reasoning_content="The user is asking me to inspect this."))),
            _Chunk(_Choice(_Delta(content="Analisi finale."), finish_reason="stop")),
        ]
    )
    provider = LMStudioProvider.__new__(LMStudioProvider)
    provider._base_url = "http://localhost:1234/v1"
    provider._healthy = True
    provider._client = _FakeClient(stream)

    events = [
        event
        async for event in provider.stream(
            model="local-model",
            messages=[{"role": "user", "content": "analizza"}],
        )
    ]

    visible_text = "".join(
        event["delta"]["text"]
        for event in events
        if event.get("type") == "content_block_delta" and event.get("delta", {}).get("type") == "text_delta"
    )
    thinking_text = "".join(
        event["delta"]["thinking"]
        for event in events
        if event.get("type") == "content_block_delta" and event.get("delta", {}).get("type") == "thinking_delta"
    )

    assert visible_text == "Analisi finale."
    assert thinking_text == "The user is asking me to inspect this."


@pytest.mark.asyncio
async def test_lmstudio_streams_openai_tool_calls() -> None:
    stream = _FakeStream(
        [
            _Chunk(_Choice(_Delta(tool_calls=[
                _ToolCallDelta(index=0, id="call_1", name="Read", arguments='{"path"'),
            ]))),
            _Chunk(_Choice(_Delta(tool_calls=[
                _ToolCallDelta(index=0, arguments=':"frontend/src/App.tsx"}'),
            ]), finish_reason="tool_calls")),
        ]
    )
    provider = LMStudioProvider.__new__(LMStudioProvider)
    provider._base_url = "http://localhost:1234/v1"
    provider._healthy = True
    provider._client = _FakeClient(stream)

    events = [
        event
        async for event in provider.stream(
            model="local-model",
            messages=[{"role": "user", "content": "leggi App"}],
            tools=[
                {
                    "name": "Read",
                    "description": "Read a file",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                }
            ],
        )
    ]

    assert provider._client.chat.completions.calls[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "Read",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]
    assert provider._client.chat.completions.calls[0]["tool_choice"] == "auto"
    assert events[:4] == [
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "call_1", "name": "Read"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"path"'},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": ':"frontend/src/App.tsx"}'},
        },
        {"type": "content_block_stop", "index": 0},
    ]
    assert events[4] == {"type": "message_delta", "delta": {"stop_reason": "tool_use"}}
