"""OpenAI-Compatible Gateway — /api/v1/chat/completions.

Allows external apps to consume TenderClaw agents through a standard API.
Supports both streaming (SSE) and non-streaming responses.

All requests are normalised through GatewayRequest before reaching the agent,
and all responses are built from GatewayResponse — ensuring REST, WS and bridge
share one contract.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents.handler import agent_handler
from backend.agents.registry import agent_registry
from backend.schemas.gateway import GatewayRequest, GatewayResponse, GatewayMessage

logger = logging.getLogger("tenderclaw.api.gateway")
router = APIRouter()


# ---------------------------------------------------------------------------
# OpenAI-compatible request/response (kept for backward compat)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "sisyphus"
    messages: list[ChatMessage]
    stream: bool = False

    def to_gateway_request(self) -> GatewayRequest:
        """Normalise into the unified contract."""
        return GatewayRequest(
            transport="rest",
            agent_name=self.model.lower(),
            messages=[GatewayMessage(role=m.role, content=m.content) for m in self.messages],
            stream=self.stream,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/models")
async def list_models() -> dict[str, Any]:
    from backend.services.model_router import model_router as mr
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "created": 1700000000, "owned_by": name}
            for name in mr.list_providers()
        ],
    }


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> Any:
    gateway_req = request.to_gateway_request()
    agent_name = gateway_req.agent_name

    try:
        agent_registry.get(agent_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent/Model not found: {agent_name}")

    if gateway_req.stream:
        return StreamingResponse(
            _stream_sse(gateway_req),
            media_type="text/event-stream",
        )

    return await _collect_response(gateway_req)


# ---------------------------------------------------------------------------
# Unified gateway endpoint (accepts GatewayRequest directly)
# ---------------------------------------------------------------------------


@router.post("/gateway")
async def gateway_endpoint(request: GatewayRequest) -> Any:
    """Single endpoint that accepts the unified GatewayRequest from any transport."""
    agent_name = request.agent_name.lower()
    try:
        agent_registry.get(agent_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    if request.stream:
        return StreamingResponse(
            _stream_sse(request),
            media_type="text/event-stream",
        )

    return await _collect_response(request)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _collect_response(gateway_req: GatewayRequest) -> dict[str, Any]:
    """Execute a turn and return a GatewayResponse serialised as OpenAI dict."""
    parts: list[str] = []
    messages = [{"role": m.role, "content": m.content} for m in gateway_req.messages]

    async for part in agent_handler.execute_agent_turn(gateway_req.agent_name, messages):
        if part.get("type") == "assistant_text":
            parts.append(part["delta"])

    resp = GatewayResponse(
        request_id=gateway_req.request_id,
        session_id=gateway_req.session_id,
        agent_name=gateway_req.agent_name,
        transport=gateway_req.transport,
        content="".join(parts),
        finish_reason="stop",
    )
    return resp.to_openai_dict()


async def _stream_sse(gateway_req: GatewayRequest) -> AsyncIterator[str]:
    """Yield OpenAI-compatible SSE chunks, built via GatewayResponse."""
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(datetime.now().timestamp())
    messages = [{"role": m.role, "content": m.content} for m in gateway_req.messages]

    async for part in agent_handler.execute_agent_turn(gateway_req.agent_name, messages):
        if part.get("type") != "assistant_text":
            continue

        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": gateway_req.agent_name,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": part["delta"]},
                "finish_reason": None,
            }],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    # Final chunk
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": gateway_req.agent_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"
