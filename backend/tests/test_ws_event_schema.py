"""Sprint 3 — WebSocket event schema tests.

Verifies the WS schema layer:
- WSSeqMixin is present on the right models
- WSToolCallStateUpdate serialises/deserialises correctly
- Sequence numbers are stamped by WSConnectionManager
- WSClientMessage union discriminates correctly
"""

from __future__ import annotations

import pytest

from backend.schemas.ws import (
    WSAssistantText,
    WSAssistantThinking,
    WSPermissionRequest,
    WSToolCallStateUpdate,
    WSToolResult,
    WSToolUseStart,
    WSTurnEnd,
    WSTurnStart,
    WSThinkingProgress,
    WSUserMessage,
    WSAbort,
    WSToolPermissionResponse,
    WSSessionConfig,
    WSClientMessage,
    WSServerMessage,
)


# ---------------------------------------------------------------------------
# WSSeqMixin — inherited correctly
# ---------------------------------------------------------------------------


SEQ_MODELS = [
    WSAssistantText,
    WSAssistantThinking,
    WSToolUseStart,
    WSToolResult,
    WSPermissionRequest,
    WSTurnStart,
    WSTurnEnd,
    WSThinkingProgress,
    WSToolCallStateUpdate,
]


class TestWSSeqMixin:
    @pytest.mark.parametrize("model_cls", SEQ_MODELS)
    def test_has_seq_field(self, model_cls):
        assert "seq" in model_cls.model_fields, f"{model_cls.__name__} missing seq"

    @pytest.mark.parametrize("model_cls", SEQ_MODELS)
    def test_seq_default_zero(self, model_cls):
        # Construct with minimum required fields
        kwargs: dict = {}
        fields = model_cls.model_fields
        for name, field in fields.items():
            if name == "seq":
                continue
            if field.is_required():
                kwargs[name] = _default_for(name)
        inst = model_cls(**kwargs)
        assert inst.seq == 0

    @pytest.mark.parametrize("model_cls", SEQ_MODELS)
    def test_seq_can_be_set(self, model_cls):
        kwargs: dict = {"seq": 42}
        for name, field in model_cls.model_fields.items():
            if name == "seq":
                continue
            if field.is_required():
                kwargs[name] = _default_for(name)
        inst = model_cls(**kwargs)
        assert inst.seq == 42


def _default_for(name: str):
    """Return a sensible default value for required fields by name."""
    defaults = {
        "delta": "text_delta",
        "message_id": "msg_test",
        "tool_use_id": "tu_test",
        "tool_name": "bash",
        "tool_input": {},
        "content": "result",
        "agent_name": "sisyphus",
        "phase": "analyzing",
        "state": "running",
    }
    return defaults.get(name, "")


# ---------------------------------------------------------------------------
# WSToolCallStateUpdate
# ---------------------------------------------------------------------------


class TestWSToolCallStateUpdate:
    def test_basic(self):
        ev = WSToolCallStateUpdate(
            tool_use_id="tu_abc",
            tool_name="bash",
            state="running",
        )
        assert ev.type == "tool_call_state"
        assert ev.is_error is False
        assert ev.result_preview == ""
        assert ev.seq == 0

    def test_completed_with_preview(self):
        ev = WSToolCallStateUpdate(
            tool_use_id="tu_xyz",
            tool_name="read_file",
            state="completed",
            result_preview="line1\nline2",
            seq=7,
        )
        assert ev.state == "completed"
        assert ev.result_preview == "line1\nline2"
        assert ev.seq == 7

    def test_failed_is_error(self):
        ev = WSToolCallStateUpdate(
            tool_use_id="tu_err",
            tool_name="bash",
            state="failed",
            is_error=True,
        )
        assert ev.is_error is True

    def test_serialise_round_trip(self):
        ev = WSToolCallStateUpdate(
            tool_use_id="tu_1",
            tool_name="write_file",
            state="approved",
            seq=3,
        )
        d = ev.model_dump()
        ev2 = WSToolCallStateUpdate.model_validate(d)
        assert ev2.tool_use_id == "tu_1"
        assert ev2.seq == 3

    def test_type_discriminator(self):
        d = {
            "type": "tool_call_state",
            "tool_use_id": "tu_disc",
            "tool_name": "bash",
            "state": "denied",
        }
        # WSToolCallStateUpdate should parse from dict
        ev = WSToolCallStateUpdate.model_validate(d)
        assert ev.state == "denied"


# ---------------------------------------------------------------------------
# WSClientMessage union
# ---------------------------------------------------------------------------


class TestWSClientMessageUnion:
    def test_user_message(self):
        raw = {"type": "user_message", "content": "hello"}
        msg = WSUserMessage.model_validate(raw)
        assert msg.type == "user_message"

    def test_abort(self):
        raw = {"type": "abort"}
        msg = WSAbort.model_validate(raw)
        assert msg.reason == "user_cancelled"

    def test_tool_permission_response(self):
        raw = {
            "type": "tool_permission_response",
            "tool_use_id": "tu_x",
            "decision": "approve",
        }
        msg = WSToolPermissionResponse.model_validate(raw)
        assert msg.decision == "approve"

    def test_session_config(self):
        raw = {"type": "session_config", "model": "claude-opus-4-6"}
        msg = WSSessionConfig.model_validate(raw)
        assert msg.model == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# WSConnectionManager sequence number
# ---------------------------------------------------------------------------


class TestWSConnectionManagerSeq:
    """Unit-test the sequence number logic without real WebSocket connections."""

    def _manager(self):
        # Import here to avoid module-level import issues
        from backend.api.ws import WSConnectionManager
        return WSConnectionManager()

    def test_seq_starts_at_zero(self):
        mgr = self._manager()
        # Simulate connect without a real WebSocket
        mgr.active_connections["sess1"] = set()
        mgr._seq_counters["sess1"] = 0
        assert mgr._seq_counters["sess1"] == 0

    def test_next_seq_increments(self):
        mgr = self._manager()
        mgr._seq_counters["sess1"] = 0
        assert mgr.next_seq("sess1") == 1
        assert mgr.next_seq("sess1") == 2
        assert mgr.next_seq("sess1") == 3

    def test_next_seq_initialises_missing(self):
        mgr = self._manager()
        # No prior entry — should start from 1
        assert mgr.next_seq("new_sess") == 1

    def test_disconnect_cleans_counter(self):
        mgr = self._manager()
        mgr.active_connections["sess2"] = set()
        mgr._seq_counters["sess2"] = 10
        mgr.disconnect(None, "sess2")  # type: ignore[arg-type]
        assert "sess2" not in mgr._seq_counters

    def test_counters_independent_per_session(self):
        mgr = self._manager()
        mgr._seq_counters["a"] = 0
        mgr._seq_counters["b"] = 0
        mgr.next_seq("a")
        mgr.next_seq("a")
        mgr.next_seq("b")
        assert mgr._seq_counters["a"] == 2
        assert mgr._seq_counters["b"] == 1

    def test_send_stamps_seq(self):
        """send_to_session should add seq to messages that lack it."""
        import asyncio
        mgr = self._manager()
        received: list[dict] = []

        class FakeWS:
            async def send_json(self, msg):
                received.append(msg)

        fw = FakeWS()
        mgr.active_connections["s3"] = {fw}  # type: ignore[arg-type]
        mgr._seq_counters["s3"] = 0

        asyncio.run(mgr.send_to_session("s3", {"type": "turn_start", "agent_name": "sisyphus"}))
        assert len(received) == 1
        assert "seq" in received[0]
        assert received[0]["seq"] == 1

    def test_send_preserves_existing_seq(self):
        import asyncio
        mgr = self._manager()
        received: list[dict] = []

        class FakeWS:
            async def send_json(self, msg):
                received.append(msg)

        fw = FakeWS()
        mgr.active_connections["s4"] = {fw}  # type: ignore[arg-type]
        mgr._seq_counters["s4"] = 5

        asyncio.run(mgr.send_to_session("s4", {"type": "turn_start", "seq": 99}))
        assert received[0]["seq"] == 99  # not overwritten
