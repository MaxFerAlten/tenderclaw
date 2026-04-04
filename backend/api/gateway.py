"""OpenAI-Compatible Gateway — /api/v1/chat/completions.

Allows external apps (like VS Code extensions or other agents) to
consume TenderClaw's specialized agents through a standard API.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.handler import agent_handler
from backend.agents.registry import agent_registry

logger = logging.getLogger("tenderclaw.api.gateway")
router = APIRouter()


class ChatMessage(BaseModel):
    """OpenAI-style chat message."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-style chat completion request."""

    model: str = "sisyphus"    # Our agent name acts as the model
    messages: list[ChatMessage]
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    """OpenAI-style chat completion response."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Standard OpenAI Chat API bridge to TenderClaw Agents."""
    agent_name = request.model.lower()
    
    try:
        agent = agent_registry.get(agent_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent/Model not found: {agent_name}")

    if request.stream:
        # TODO: Implement streaming (AsyncIterable wrapper)
        raise HTTPException(status_code=400, detail="Streaming not yet supported in Gateway.")

    # Convert messages to internal format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Run one turn and collect text (simplified for Gateway)
    results = []
    async for part in agent_handler.execute_agent_turn(agent_name, messages):
        if part.get("type") == "assistant_text":
            results.append(part["delta"])
    
    full_text = "".join(results)

    return ChatCompletionResponse(
        model=agent_name,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": full_text},
            "finish_reason": "stop"
        }],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
