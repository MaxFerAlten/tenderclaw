"""Sprint 3 — Gateway contract tests.

Verifies that GatewayRequest / GatewayResponse correctly represent any
transport, and that the factory helpers produce the right shapes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.gateway import (
    GatewayAttachment,
    GatewayEvent,
    GatewayMessage,
    GatewayRequest,
    GatewayResponse,
)


# ---------------------------------------------------------------------------
# GatewayMessage
# ---------------------------------------------------------------------------


class TestGatewayMessage:
    def test_basic_user_message(self):
        m = GatewayMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"
        assert m.tool_use_id is None

    def test_tool_result_message(self):
        m = GatewayMessage(role="tool", content="ok", tool_use_id="tu_abc")
        assert m.role == "tool"
        assert m.tool_use_id == "tu_abc"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            GatewayMessage(role="unknown", content="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GatewayRequest — field defaults
# ---------------------------------------------------------------------------


class TestGatewayRequestDefaults:
    def test_defaults(self):
        req = GatewayRequest()
        assert req.transport == "rest"
        assert req.agent_name == "sisyphus"
        assert req.stream is False
        assert req.session_id is None
        assert req.messages == []
        assert req.attachments == []
        assert req.metadata == {}

    def test_request_id_auto_generated(self):
        r1 = GatewayRequest()
        r2 = GatewayRequest()
        assert r1.request_id != r2.request_id

    def test_transport_values(self):
        for t in ("rest", "ws", "bridge", "relay"):
            req = GatewayRequest(transport=t)  # type: ignore[arg-type]
            assert req.transport == t

    def test_invalid_transport(self):
        with pytest.raises(ValidationError):
            GatewayRequest(transport="grpc")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GatewayRequest — factory helpers
# ---------------------------------------------------------------------------


class TestGatewayRequestFromOpenAI:
    """from_openai() maps ChatCompletionRequest → GatewayRequest."""

    def _make_openai_req(self, model="sisyphus", messages=None, stream=False):
        from types import SimpleNamespace
        msgs = messages or [SimpleNamespace(role="user", content="hi")]
        return SimpleNamespace(model=model, messages=msgs, stream=stream)

    def test_basic_mapping(self):
        req = GatewayRequest.from_openai(self._make_openai_req())
        assert req.transport == "rest"
        assert req.agent_name == "sisyphus"
        assert len(req.messages) == 1
        assert req.messages[0].role == "user"

    def test_model_sets_agent_name(self):
        req = GatewayRequest.from_openai(self._make_openai_req(model="oracle"))
        assert req.agent_name == "oracle"

    def test_stream_propagated(self):
        req = GatewayRequest.from_openai(self._make_openai_req(stream=True))
        assert req.stream is True

    def test_session_id(self):
        req = GatewayRequest.from_openai(self._make_openai_req(), session_id="sess_123")
        assert req.session_id == "sess_123"

    def test_multiple_messages(self):
        from types import SimpleNamespace
        msgs = [
            SimpleNamespace(role="system", content="you are helpful"),
            SimpleNamespace(role="user", content="hello"),
        ]
        req = GatewayRequest.from_openai(self._make_openai_req(messages=msgs))
        assert len(req.messages) == 2
        assert req.messages[0].role == "system"


class TestGatewayRequestFromWS:
    def _make_ws_msg(self, content="hi", attachments=None):
        from types import SimpleNamespace
        return SimpleNamespace(content=content, attachments=attachments or [])

    def test_basic(self):
        req = GatewayRequest.from_ws(self._make_ws_msg(), session_id="sess_ws")
        assert req.transport == "ws"
        assert req.stream is True
        assert req.session_id == "sess_ws"
        assert req.messages[0].content == "hi"

    def test_custom_agent(self):
        req = GatewayRequest.from_ws(self._make_ws_msg(), session_id="s", agent_name="oracle")
        assert req.agent_name == "oracle"

    def test_attachment_forwarded(self):
        from types import SimpleNamespace
        att = SimpleNamespace(type="image/png", url="data:...", name="screenshot.png")
        req = GatewayRequest.from_ws(self._make_ws_msg(attachments=[att]), session_id="s")
        assert len(req.attachments) == 1
        assert req.attachments[0].type == "image/png"


class TestGatewayRequestFromRelay:
    def _make_relay_req(self, content="task text", agent_override=None, sender="bot"):
        from types import SimpleNamespace
        return SimpleNamespace(content=content, agent_override=agent_override, sender=sender)

    def test_basic(self):
        req = GatewayRequest.from_relay(self._make_relay_req(), session_id="relay_sess")
        assert req.transport == "relay"
        assert req.stream is True
        assert req.messages[0].content == "task text"
        assert req.metadata["sender"] == "bot"

    def test_agent_override(self):
        req = GatewayRequest.from_relay(
            self._make_relay_req(agent_override="metis"), session_id="s"
        )
        assert req.agent_name == "metis"

    def test_no_override_defaults_sisyphus(self):
        req = GatewayRequest.from_relay(self._make_relay_req(), session_id="s")
        assert req.agent_name == "sisyphus"


# ---------------------------------------------------------------------------
# GatewayResponse
# ---------------------------------------------------------------------------


class TestGatewayResponse:
    def test_defaults(self):
        resp = GatewayResponse()
        assert resp.agent_name == "sisyphus"
        assert resp.finish_reason == "stop"
        assert resp.content == ""
        assert resp.error is None

    def test_response_id_unique(self):
        r1 = GatewayResponse()
        r2 = GatewayResponse()
        assert r1.response_id != r2.response_id

    def test_to_openai_dict_shape(self):
        resp = GatewayResponse(
            agent_name="oracle",
            content="here is the answer",
            input_tokens=100,
            output_tokens=50,
        )
        d = resp.to_openai_dict()
        assert d["object"] == "chat.completion"
        assert d["model"] == "oracle"
        assert d["choices"][0]["message"]["content"] == "here is the answer"
        assert d["choices"][0]["message"]["role"] == "assistant"
        assert d["usage"]["prompt_tokens"] == 100
        assert d["usage"]["completion_tokens"] == 50
        assert d["usage"]["total_tokens"] == 150

    def test_to_openai_dict_id_prefix(self):
        resp = GatewayResponse()
        d = resp.to_openai_dict()
        assert d["id"].startswith("chatcmpl-")


# ---------------------------------------------------------------------------
# GatewayEvent
# ---------------------------------------------------------------------------


class TestGatewayEvent:
    def test_defaults(self):
        ev = GatewayEvent(event_type="assistant_text")
        assert ev.sequence == 0
        assert ev.data == {}

    def test_with_data(self):
        ev = GatewayEvent(event_type="tool_result", data={"result": "ok"}, sequence=5)
        assert ev.data["result"] == "ok"
        assert ev.sequence == 5
