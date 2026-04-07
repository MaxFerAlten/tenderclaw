"""OpenCode provider — OpenCode Zen models."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.config import settings
from backend.schemas.messages import TokenUsage
from backend.services.providers.base import BaseProvider
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.providers.opencode")

OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"


class OpenCodeProvider(BaseProvider):
    """Provider for OpenCode Zen models."""

    name = "opencode"
    models = ["opencode"]

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.opencode_api_key
        if not key:
            raise ProviderError("OPENCODE_API_KEY not set")
        self._client = AsyncOpenAI(
            api_key=key,
            base_url=OPENCODE_BASE_URL,
        )

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completion from OpenCode, normalized to TenderClaw format."""
        oai_messages: list[dict[str, Any]] = []

        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                oai_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            oai_content.append({"type": "text", "text": part.get("text", "")})
                        elif part.get("type") == "image_url":
                            img_url = part.get("image_url", {}).get("url", "")
                            if img_url:
                                oai_content.append({"type": "image_url", "image_url": {"url": img_url}})
                    elif isinstance(part, str):
                        oai_content.append({"type": "text", "text": part})
                if oai_content:
                    oai_messages.append({"role": role, "content": oai_content})
                else:
                    oai_messages.append({"role": role, "content": ""})
            else:
                oai_messages.append(
                    {
                        "role": role,
                        "content": str(content) if content else "",
                    }
                )

        oai_tools = _convert_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if oai_tools:
            kwargs["tools"] = oai_tools

        try:
            stream = await self._client.chat.completions.create(**kwargs)

            pending_tool_id: str | None = None
            pending_tool_name: str = ""
            started_tools: set[str] = set()

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_id = tc.id or ""
                        tc_name = tc.function.name or ""
                        tc_args = tc.function.arguments or ""

                        if tc_name and not pending_tool_id:
                            pending_tool_id = tc_id or f"tool_{id(tc)}"
                            pending_tool_name = tc_name
                            if pending_tool_id not in started_tools:
                                started_tools.add(pending_tool_id)
                                yield {
                                    "type": "content_block_start",
                                    "content_block": {
                                        "type": "tool_use",
                                        "id": pending_tool_id,
                                        "name": pending_tool_name,
                                    },
                                }
                        if tc_args:
                            yield {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {"type": "input_json_delta", "partial_json": tc_args},
                            }

                elif delta and delta.content:
                    text = delta.content
                    if text:
                        yield {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": text},
                        }

                if choice.finish_reason:
                    if pending_tool_id:
                        yield {"type": "content_block_stop"}
                    yield {
                        "type": "message_delta",
                        "delta": {"stop_reason": _map_finish_reason(choice.finish_reason)},
                    }
                    pending_tool_id = None
                    pending_tool_name = ""

            if pending_tool_id:
                yield {"type": "content_block_stop"}

            yield {
                "type": "usage",
                "usage": TokenUsage(input_tokens=0, output_tokens=0),
            }

        except Exception as exc:
            logger.error("OpenCode API error: %s", exc)
            raise ProviderError(f"OpenCode API error: {exc}") from exc


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-format tools to OpenAI function-calling format."""
    oai_tools = []
    for tool in tools:
        oai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
        )
    return oai_tools


def _map_finish_reason(reason: str) -> str:
    """Map OpenAI finish reasons to Anthropic-compatible ones."""
    mapping = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }
    return mapping.get(reason, "end_turn")
