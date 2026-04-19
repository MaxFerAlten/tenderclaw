"""OpenRouter provider — OpenCode Zen models."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.config import settings
from backend.schemas.messages import TokenUsage
from backend.services.providers.base import BaseProvider
from backend.services.power_levels import PowerProfile
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.providers.openrouter")

OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"


class OpenRouterProvider(BaseProvider):
    """Provider for OpenCode Zen models."""

    name = "openrouter"
    models = ["openrouter"]

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.openrouter_api_key
        if not key:
            raise ProviderError("OPENROUTER_API_KEY not set")
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
        power_profile: PowerProfile | None = None,
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
                tool_calls = []
                tool_results = []
                for part in content:
                    if isinstance(part, dict):
                        ptype = part.get("type")
                        if ptype == "text":
                            oai_content.append({"type": "text", "text": part.get("text", "")})
                        elif ptype == "image_url":
                            img_url = part.get("image_url", {}).get("url", "")
                            if img_url:
                                oai_content.append({"type": "image_url", "image_url": {"url": img_url}})
                        elif ptype == "tool_use":
                            tool_calls.append({
                                "id": part.get("id"),
                                "type": "function",
                                "function": {
                                    "name": part.get("name"),
                                    "arguments": json.dumps(part.get("input", {})),
                                },
                            })
                        elif ptype == "tool_result":
                            tool_results.append({
                                "role": "tool",
                                "tool_call_id": part.get("tool_use_id"),
                                "content": str(part.get("content", "")),
                            })
                    elif isinstance(part, str):
                        oai_content.append({"type": "text", "text": part})

                # Append assistant message with tool calls if any
                if role == "assistant" and tool_calls:
                    msg_dict = {
                        "role": "assistant",
                        "content": _text_content(oai_content) or None,
                    }
                    msg_dict["tool_calls"] = tool_calls
                    oai_messages.append(msg_dict)
                elif role == "assistant" and oai_content:
                    oai_messages.append({"role": role, "content": _text_content(oai_content)})
                # Append normal content if not an assistant tool_call message
                elif oai_content:
                    oai_messages.append({"role": role, "content": oai_content})
                elif not tool_results and not tool_calls:
                    oai_messages.append({"role": role, "content": ""})

                # Append tool results as separate 'tool' role messages
                if tool_results:
                    for tr in tool_results:
                        oai_messages.append(tr)
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

            # Index-based accumulator: handles OpenAI-compatible streaming for
            # single and parallel tool calls. Some providers send id/name and
            # argument chunks in separate deltas, so keep unsent args until the
            # content block can be safely opened.
            tool_acc: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        if idx not in tool_acc:
                            tool_acc[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "args_parts": [],
                                "sent_arg_parts": 0,
                                "emitted": False,
                            }
                        entry = tool_acc[idx]
                        # id/name commonly arrive first, but OpenAI-compatible
                        # gateways are allowed to split them across chunks.
                        if tc.id:
                            entry["id"] = tc.id
                        if tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function.arguments:
                            entry["args_parts"].append(tc.function.arguments)

                        # Emit content_block_start once we know the real tool
                        # id and name. If the gateway never sends an id, a
                        # stable fallback is assigned at finish_reason below.
                        if entry["id"] and entry["name"] and not entry["emitted"]:
                            entry["emitted"] = True
                            logger.debug(
                                "OpenCode tool_call start: idx=%d id=%s name=%s",
                                idx, entry["id"], entry["name"],
                            )
                            yield {
                                "type": "content_block_start",
                                "index": idx,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": entry["id"],
                                    "name": entry["name"],
                                },
                            }

                        # Stream any args collected since the block opened.
                        if entry["emitted"]:
                            for part in entry["args_parts"][entry["sent_arg_parts"]:]:
                                yield {
                                    "type": "content_block_delta",
                                    "index": idx,
                                    "delta": {
                                        "type": "input_json_delta",
                                        "partial_json": part,
                                    },
                                }
                            entry["sent_arg_parts"] = len(entry["args_parts"])

                elif delta and delta.content:
                    text = delta.content
                    if text:
                        yield {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": text},
                        }

                if choice.finish_reason:
                    # Close all open tool blocks in index order
                    for _idx in sorted(tool_acc):
                        entry = tool_acc[_idx]
                        if not entry["emitted"] and entry["name"]:
                            entry["id"] = entry["id"] or f"tool_{_idx}_{id(chunk)}"
                            entry["emitted"] = True
                            yield {
                                "type": "content_block_start",
                                "index": _idx,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": entry["id"],
                                    "name": entry["name"],
                                },
                            }
                            for part in entry["args_parts"][entry["sent_arg_parts"]:]:
                                yield {
                                    "type": "content_block_delta",
                                    "index": _idx,
                                    "delta": {
                                        "type": "input_json_delta",
                                        "partial_json": part,
                                    },
                                }
                            entry["sent_arg_parts"] = len(entry["args_parts"])
                        if entry["emitted"]:
                            yield {"type": "content_block_stop", "index": _idx}
                    tool_acc.clear()

                    mapped = _map_finish_reason(choice.finish_reason)
                    logger.debug("OpenCode finish_reason=%s → %s", choice.finish_reason, mapped)
                    yield {
                        "type": "message_delta",
                        "delta": {"stop_reason": mapped},
                    }

            # Safety: close any tool blocks not finished via finish_reason
            for _idx in sorted(tool_acc):
                entry = tool_acc[_idx]
                if not entry["emitted"] and entry["name"]:
                    entry["id"] = entry["id"] or f"tool_{_idx}_final"
                    yield {
                        "type": "content_block_start",
                        "index": _idx,
                        "content_block": {
                            "type": "tool_use",
                            "id": entry["id"],
                            "name": entry["name"],
                        },
                    }
                    for part in entry["args_parts"][entry["sent_arg_parts"]:]:
                        yield {
                            "type": "content_block_delta",
                            "index": _idx,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": part,
                            },
                        }
                    entry["emitted"] = True
                    entry["sent_arg_parts"] = len(entry["args_parts"])
                if entry["emitted"]:
                    yield {"type": "content_block_stop", "index": _idx}

            yield {
                "type": "usage",
                "usage": TokenUsage(input_tokens=0, output_tokens=0),
            }

        except Exception as exc:
                logger.error("OpenRouter API error: %s", exc)
                raise ProviderError(f"OpenRouter API error: {exc}") from exc


def _text_content(content: list[dict[str, Any]]) -> str:
    """Flatten text content blocks for assistant history messages."""
    return "\n".join(str(part.get("text", "")) for part in content if part.get("type") == "text").strip()


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
