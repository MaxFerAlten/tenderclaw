"""OpenAI-Compatible Gateway — /api/v1/chat/completions.

Allows external apps to consume TenderClaw agents through a standard API.
Supports both streaming (SSE) and non-streaming responses.
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

logger = logging.getLogger("tenderclaw.api.gateway")
router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "sisyphus"
    messages: list[ChatMessage]
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)


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
    agent_name = request.model.lower()
    try:
        agent_registry.get(agent_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent/Model not found: {agent_name}")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.stream:
        return StreamingResponse(
            _stream_sse(agent_name, messages),
            media_type="text/event-stream",
        )

    return await _collect_response(agent_name, messages)


async def _collect_response(agent_name: str, messages: list[dict]) -> ChatCompletionResponse:
    parts: list[str] = []
    async for part in agent_handler.execute_agent_turn(agent_name, messages):
        if part.get("type") == "assistant_text":
            parts.append(part["delta"])

    return ChatCompletionResponse(
        model=agent_name,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": "".join(parts)},
            "finish_reason": "stop",
        }],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )


async def _stream_sse(agent_name: str, messages: list[dict]) -> AsyncIterator[str]:
    """Yield OpenAI-compatible SSE chunks."""
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(datetime.now().timestamp())

    async for part in agent_handler.execute_agent_turn(agent_name, messages):
        if part.get("type") != "assistant_text":
            continue

        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": agent_name,
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
        "model": agent_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"
