"""Gateway contract — unified request/response models shared by REST, WS and bridge.

All three transport layers (REST /chat/completions, WebSocket, remote bridge) must
express incoming requests and outgoing responses through these types so that a
single conversation turn is representable regardless of transport.

Usage:
    # REST handler
    from backend.schemas.gateway import GatewayRequest, GatewayResponse
    req = GatewayRequest.from_openai(openai_request)

    # WS handler
    req = GatewayRequest.from_ws(ws_user_message)

    # Bridge handler
    req = GatewayRequest.from_relay(relay_task)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Unified request
# ---------------------------------------------------------------------------


class GatewayAttachment(BaseModel):
    """A file or image attachment bundled with a request."""

    type: str                  # MIME type, e.g. "image/png"
    url: str | None = None
    name: str | None = None


class GatewayMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_use_id: str | None = None  # for tool-result messages


class GatewayRequest(BaseModel):
    """Canonical request that every transport maps into before processing.

    Fields:
        request_id:     Unique ID for deduplication and tracing.
        transport:      Origin transport — "rest" | "ws" | "bridge" | "relay".
        session_id:     Active session, or None for stateless REST calls.
        agent_name:     Target agent (defaults to "sisyphus").
        messages:       Full conversation history.
        stream:         Whether the caller expects streaming responses.
        attachments:    Optional file/image attachments.
        agent_override: Temporary agent switch for this request only.
        metadata:       Transport-specific extras (auth, sender, etc.).
    """

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    transport: Literal["rest", "ws", "bridge", "relay"] = "rest"
    session_id: str | None = None
    agent_name: str = "sisyphus"
    messages: list[GatewayMessage] = Field(default_factory=list)
    stream: bool = False
    attachments: list[GatewayAttachment] = Field(default_factory=list)
    agent_override: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ---------------------------------------------------------------------------
    # Factory helpers
    # ---------------------------------------------------------------------------

    @classmethod
    def from_openai(cls, openai_req: Any, session_id: str | None = None) -> "GatewayRequest":
        """Build from an OpenAI-compatible ChatCompletionRequest."""
        messages = [
            GatewayMessage(role=m.role, content=m.content)
            for m in openai_req.messages
        ]
        return cls(
            transport="rest",
            session_id=session_id,
            agent_name=openai_req.model,
            messages=messages,
            stream=openai_req.stream,
        )

    @classmethod
    def from_ws(cls, ws_msg: Any, session_id: str, agent_name: str = "sisyphus") -> "GatewayRequest":
        """Build from a WSUserMessage."""
        return cls(
            transport="ws",
            session_id=session_id,
            agent_name=agent_name,
            messages=[GatewayMessage(role="user", content=ws_msg.content)],
            stream=True,
            attachments=[
                GatewayAttachment(type=a.type, url=a.url, name=a.name)
                for a in getattr(ws_msg, "attachments", [])
            ],
        )

    @classmethod
    def from_relay(cls, relay_req: Any, session_id: str) -> "GatewayRequest":
        """Build from a RelayTaskRequest."""
        return cls(
            transport="relay",
            session_id=session_id,
            agent_name=relay_req.agent_override or "sisyphus",
            messages=[GatewayMessage(role="user", content=relay_req.content)],
            stream=True,
            metadata={"sender": relay_req.sender},
        )


# ---------------------------------------------------------------------------
# Unified response
# ---------------------------------------------------------------------------


class GatewayEvent(BaseModel):
    """A single streamed event from a processing turn."""

    event_type: str            # matches WS `type` field
    data: dict[str, Any] = Field(default_factory=dict)
    sequence: int = 0          # incremented per-session for loss detection


class GatewayResponse(BaseModel):
    """Canonical response envelope returned by all transports.

    For streaming callers this is populated incrementally via GatewayEvent.
    For non-streaming callers the full `content` is populated at the end.
    """

    response_id: str = Field(default_factory=lambda: uuid4().hex)
    request_id: str = ""
    session_id: str | None = None
    agent_name: str = "sisyphus"
    transport: Literal["rest", "ws", "bridge", "relay"] = "rest"

    # Non-streaming (collected)
    content: str = ""
    finish_reason: str = "stop"

    # Usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0

    created_at: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None

    def to_openai_dict(self) -> dict[str, Any]:
        """Serialize to an OpenAI-compatible chat.completion object."""
        return {
            "id": f"chatcmpl-{self.response_id}",
            "object": "chat.completion",
            "created": int(self.created_at.timestamp()),
            "model": self.agent_name,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": self.content},
                "finish_reason": self.finish_reason,
            }],
            "usage": {
                "prompt_tokens": self.input_tokens,
                "completion_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
        }
