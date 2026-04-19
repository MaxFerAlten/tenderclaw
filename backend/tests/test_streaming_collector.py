from __future__ import annotations

from backend.core.streaming import StreamCollector


async def test_stream_collector_keeps_parallel_tool_json_separate():
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    collector = StreamCollector(message_id="msg_parallel", send=send)

    await collector.process({
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "tool_use", "id": "tu_glob", "name": "Glob"},
    })
    await collector.process({
        "type": "content_block_start",
        "index": 1,
        "content_block": {"type": "tool_use", "id": "tu_read", "name": "Read"},
    })
    await collector.process({
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "input_json_delta", "partial_json": '{"pattern":"*.py"'},
    })
    await collector.process({
        "type": "content_block_delta",
        "index": 1,
        "delta": {"type": "input_json_delta", "partial_json": '{"path":"README.md"'},
    })
    await collector.process({
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "input_json_delta", "partial_json": '}'},
    })
    await collector.process({
        "type": "content_block_delta",
        "index": 1,
        "delta": {"type": "input_json_delta", "partial_json": '}'},
    })
    await collector.process({"type": "content_block_stop", "index": 0})
    await collector.process({"type": "content_block_stop", "index": 1})

    assert [(tu.id, tu.name, tu.input) for tu in collector.tool_uses] == [
        ("tu_glob", "Glob", {"pattern": "*.py"}),
        ("tu_read", "Read", {"path": "README.md"}),
    ]
    # tool_use_start + input_json_delta events are sent to frontend
    assert [event["tool_use_id"] for event in sent] == [
        "tu_glob", "tu_read",  # tool_use_start
        "tu_glob", "tu_read",  # first json delta each
        "tu_glob", "tu_read",  # closing brace delta each
    ]


async def test_stream_collector_hides_unclosed_antthinking_block():
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    collector = StreamCollector(message_id="msg_thinking", send=send)

    await collector.process({
        "type": "content_block_delta",
        "delta": {
            "type": "text_delta",
            "text": (
                "Analizzo il codice.\n\n"
                "<antThinking>The user is asking me to inspect this.\n"
                "Analizzo il codice di TenderClaw."
            ),
        },
    })
    await collector.process({"type": "message_delta", "delta": {"stop_reason": "stop"}})

    visible = "".join(event["delta"] for event in sent if event["type"] == "assistant_text")
    assert visible == "Analizzo il codice.\n\n"
    assert "antThinking" not in visible
    assert "The user is asking me" not in visible


async def test_stream_collector_hides_split_hidden_thinking_tags():
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    collector = StreamCollector(message_id="msg_split", send=send)

    await collector.process({
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "Risposta visibile. <ant"},
    })
    await collector.process({
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "Thinking>privato</antThinking> Fine."},
    })
    await collector.process({"type": "message_delta", "delta": {"stop_reason": "stop"}})

    visible = "".join(event["delta"] for event in sent if event["type"] == "assistant_text")
    assert visible == "Risposta visibile.  Fine."
    assert "privato" not in visible
    assert "antThinking" not in visible
