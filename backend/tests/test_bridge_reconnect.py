"""Sprint 3 — Bridge / relay reconnect and transport contract tests.

Verifies:
- GatewayRequest.from_relay() maps relay tasks correctly
- Transport field is carried through to GatewayResponse
- GatewayResponse.to_openai_dict() is stable across transports
- Metadata is preserved (e.g. sender field)
- agent_override routing logic
- Session ID propagation across factory helpers
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from backend.schemas.gateway import GatewayRequest, GatewayResponse, GatewayMessage


# ---------------------------------------------------------------------------
# Relay / Bridge transport
# ---------------------------------------------------------------------------


def _relay(content="do something", agent_override=None, sender="remote_bot"):
    return SimpleNamespace(content=content, agent_override=agent_override, sender=sender)


class TestRelayTransport:
    def test_transport_is_relay(self):
        req = GatewayRequest.from_relay(_relay(), session_id="sess_r1")
        assert req.transport == "relay"

    def test_stream_always_true(self):
        req = GatewayRequest.from_relay(_relay(), session_id="sess_r1")
        assert req.stream is True

    def test_content_in_messages(self):
        req = GatewayRequest.from_relay(_relay(content="deploy now"), session_id="s")
        assert req.messages[0].role == "user"
        assert req.messages[0].content == "deploy now"

    def test_sender_in_metadata(self):
        req = GatewayRequest.from_relay(_relay(sender="ci_agent"), session_id="s")
        assert req.metadata["sender"] == "ci_agent"

    def test_agent_override_used(self):
        req = GatewayRequest.from_relay(_relay(agent_override="sentinel"), session_id="s")
        assert req.agent_name == "sentinel"

    def test_no_override_defaults_sisyphus(self):
        req = GatewayRequest.from_relay(_relay(), session_id="s")
        assert req.agent_name == "sisyphus"

    def test_session_id_stored(self):
        req = GatewayRequest.from_relay(_relay(), session_id="relay_42")
        assert req.session_id == "relay_42"

    def test_request_id_is_unique(self):
        r1 = GatewayRequest.from_relay(_relay(), session_id="s")
        r2 = GatewayRequest.from_relay(_relay(), session_id="s")
        assert r1.request_id != r2.request_id


# ---------------------------------------------------------------------------
# WS transport
# ---------------------------------------------------------------------------


def _ws_msg(content="hello ws", attachments=None):
    return SimpleNamespace(content=content, attachments=attachments or [])


class TestWSTransport:
    def test_transport_is_ws(self):
        req = GatewayRequest.from_ws(_ws_msg(), session_id="ws_sess")
        assert req.transport == "ws"

    def test_stream_always_true(self):
        req = GatewayRequest.from_ws(_ws_msg(), session_id="ws_sess")
        assert req.stream is True

    def test_content_in_messages(self):
        req = GatewayRequest.from_ws(_ws_msg(content="run tests"), session_id="s")
        assert req.messages[0].content == "run tests"

    def test_agent_name_default(self):
        req = GatewayRequest.from_ws(_ws_msg(), session_id="s")
        assert req.agent_name == "sisyphus"

    def test_agent_name_override(self):
        req = GatewayRequest.from_ws(_ws_msg(), session_id="s", agent_name="metis")
        assert req.agent_name == "metis"

    def test_attachment_mapping(self):
        att = SimpleNamespace(type="text/plain", url=None, name="notes.txt")
        req = GatewayRequest.from_ws(_ws_msg(attachments=[att]), session_id="s")
        assert len(req.attachments) == 1
        assert req.attachments[0].name == "notes.txt"


# ---------------------------------------------------------------------------
# REST transport
# ---------------------------------------------------------------------------


def _openai_req(model="sisyphus", messages=None, stream=False):
    msgs = messages or [SimpleNamespace(role="user", content="hi")]
    return SimpleNamespace(model=model, messages=msgs, stream=stream)


class TestRESTTransport:
    def test_transport_is_rest(self):
        req = GatewayRequest.from_openai(_openai_req())
        assert req.transport == "rest"

    def test_stream_false_by_default(self):
        req = GatewayRequest.from_openai(_openai_req())
        assert req.stream is False

    def test_stream_true_propagated(self):
        req = GatewayRequest.from_openai(_openai_req(stream=True))
        assert req.stream is True


# ---------------------------------------------------------------------------
# GatewayResponse transport propagation
# ---------------------------------------------------------------------------


class TestResponseTransportPropagation:
    @pytest.mark.parametrize("transport", ["rest", "ws", "bridge", "relay"])
    def test_transport_stored(self, transport):
        resp = GatewayResponse(transport=transport)  # type: ignore[arg-type]
        assert resp.transport == transport

    def test_to_openai_dict_stable_across_transports(self):
        for transport in ("rest", "ws", "bridge", "relay"):
            resp = GatewayResponse(
                agent_name="sisyphus",
                content="ok",
                transport=transport,  # type: ignore[arg-type]
            )
            d = resp.to_openai_dict()
            assert d["choices"][0]["message"]["content"] == "ok"
            assert d["model"] == "sisyphus"


# ---------------------------------------------------------------------------
# Session ID round-trip
# ---------------------------------------------------------------------------


class TestSessionIdRoundTrip:
    def test_rest_session_id(self):
        req = GatewayRequest.from_openai(_openai_req(), session_id="sess_abc")
        resp = GatewayResponse(session_id=req.session_id, request_id=req.request_id)
        assert resp.session_id == "sess_abc"
        assert resp.request_id == req.request_id

    def test_ws_session_id(self):
        req = GatewayRequest.from_ws(_ws_msg(), session_id="sess_ws_42")
        resp = GatewayResponse(session_id=req.session_id, request_id=req.request_id)
        assert resp.session_id == "sess_ws_42"

    def test_relay_session_id(self):
        req = GatewayRequest.from_relay(_relay(), session_id="sess_relay_7")
        resp = GatewayResponse(session_id=req.session_id, request_id=req.request_id)
        assert resp.session_id == "sess_relay_7"


# ---------------------------------------------------------------------------
# Message history preservation
# ---------------------------------------------------------------------------


class TestMessageHistory:
    def test_multi_turn_openai(self):
        msgs = [
            SimpleNamespace(role="system", content="be helpful"),
            SimpleNamespace(role="user", content="question"),
            SimpleNamespace(role="assistant", content="answer"),
            SimpleNamespace(role="user", content="follow-up"),
        ]
        req = GatewayRequest.from_openai(_openai_req(messages=msgs))
        assert len(req.messages) == 4
        assert req.messages[2].role == "assistant"

    def test_ws_always_single_message(self):
        req = GatewayRequest.from_ws(_ws_msg(content="single turn"), session_id="s")
        assert len(req.messages) == 1

    def test_gateway_request_direct_messages(self):
        req = GatewayRequest(
            transport="rest",
            messages=[
                GatewayMessage(role="user", content="hi"),
                GatewayMessage(role="assistant", content="hello"),
            ],
        )
        assert len(req.messages) == 2
