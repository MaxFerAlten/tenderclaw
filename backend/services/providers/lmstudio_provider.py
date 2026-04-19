"""LM Studio provider — local models via LM Studio.

Uses the OpenAI-compatible API that LM Studio exposes at localhost:1234.
"""

from __future__ import annotations

import json
import logging
import urllib.request as _urlreq
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.config import settings
from backend.schemas.messages import TokenUsage
from backend.services.providers.base import BaseProvider
from backend.services.power_levels import PowerProfile
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.providers.lmstudio")


class LMStudioProvider(BaseProvider):
    """Provider for local LM Studio models."""

    name = "lmstudio"
    models = ["lmstudio"]

    def __init__(self, base_url: str | None = None) -> None:
        url = base_url or settings.lmstudio_base_url
        if not url.endswith("/v1"):
            url = url.rstrip("/") + "/v1"
        self._base_url = url
        self._healthy = False
        try:
            probe = self._base_url.rstrip("/") + "/models"
            with _urlreq.urlopen(probe, timeout=2) as resp:
                if resp.status == 200:
                    self._healthy = True
        except Exception:
            self._healthy = False
        self._client = AsyncOpenAI(api_key="lm-studio", base_url=self._base_url)
        logger.info("LM Studio provider initialized with base_url: %s", self._base_url)

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
        power_profile: PowerProfile | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completion from LM Studio."""
        oai_messages = _to_openai_messages(messages, system=system)
        oai_tools = _convert_tools(tools) if tools else None

        if not getattr(self, "_healthy", True):
            raise ProviderError(f"LM Studio not healthy or not reachable at {self._base_url}")

        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": oai_messages,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if oai_tools:
                kwargs["tools"] = oai_tools
                kwargs["tool_choice"] = "auto"

            stream = await self._client.chat.completions.create(**kwargs)
            tool_acc: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = choice.delta

                tool_calls = getattr(delta, "tool_calls", None) if delta else None
                if tool_calls:
                    for event in _collect_tool_call_events(tool_calls, tool_acc, chunk):
                        yield event

                content = delta.content if delta else ""
                reasoning = getattr(delta, "reasoning_content", None) if delta else None

                if reasoning:
                    yield {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "thinking_delta", "thinking": reasoning},
                    }

                if content:
                    yield {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content},
                    }
                if choice.finish_reason:
                    for event in _finish_tool_calls(tool_acc, chunk):
                        yield event
                    yield {
                        "type": "message_delta",
                        "delta": {"stop_reason": _map_finish_reason(choice.finish_reason)},
                    }

            for event in _finish_tool_calls(tool_acc, None):
                yield event

            yield {"type": "usage", "usage": TokenUsage()}

        except Exception as exc:
            logger.error("LM Studio error: %s", exc)
            raise ProviderError(
                f"LM Studio error: {exc}. Is LM Studio running at {settings.lmstudio_base_url}?"
            ) from exc


def _to_openai_messages(messages: list[dict[str, Any]], *, system: str = "") -> list[dict[str, Any]]:
    oai_messages: list[dict[str, Any]] = []
    if system:
        oai_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            oai_content: list[dict[str, Any]] = []
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            for part in content:
                if isinstance(part, str):
                    oai_content.append({"type": "text", "text": part})
                    continue
                if not isinstance(part, dict):
                    continue

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

            if role == "assistant" and tool_calls:
                msg_dict: dict[str, Any] = {
                    "role": "assistant",
                    "content": _text_content(oai_content) or None,
                    "tool_calls": tool_calls,
                }
                oai_messages.append(msg_dict)
            elif role == "assistant" and oai_content:
                oai_messages.append({"role": role, "content": _text_content(oai_content)})
            elif oai_content:
                oai_messages.append({"role": role, "content": oai_content})
            elif not tool_results and not tool_calls:
                oai_messages.append({"role": role, "content": ""})

            oai_messages.extend(tool_results)
        else:
            oai_messages.append({"role": role, "content": str(content) if content else ""})

    return oai_messages


def _text_content(content: list[dict[str, Any]]) -> str:
    """Flatten text content blocks for assistant history messages."""
    return "\n".join(str(part.get("text", "")) for part in content if part.get("type") == "text").strip()


def _collect_tool_call_events(
    tool_calls: list[Any],
    tool_acc: dict[int, dict[str, Any]],
    chunk: Any,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for tc in tool_calls:
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
        if tc.id:
            entry["id"] = tc.id
        if tc.function.name:
            entry["name"] = tc.function.name
        if tc.function.arguments:
            entry["args_parts"].append(tc.function.arguments)

        if not entry["emitted"] and entry["name"]:
            entry["id"] = entry["id"] or f"tool_{idx}_{id(chunk)}"
            entry["emitted"] = True
            events.append({
                "type": "content_block_start",
                "index": idx,
                "content_block": {
                    "type": "tool_use",
                    "id": entry["id"],
                    "name": entry["name"],
                },
            })

        if entry["emitted"]:
            for part in entry["args_parts"][entry["sent_arg_parts"]:]:
                events.append({
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": part,
                    },
                })
            entry["sent_arg_parts"] = len(entry["args_parts"])

    return events


def _finish_tool_calls(tool_acc: dict[int, dict[str, Any]], chunk: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for idx in sorted(tool_acc):
        entry = tool_acc[idx]
        if not entry["emitted"] and entry["name"]:
            entry["id"] = entry["id"] or f"tool_{idx}_{id(chunk)}"
            entry["emitted"] = True
            events.append({
                "type": "content_block_start",
                "index": idx,
                "content_block": {
                    "type": "tool_use",
                    "id": entry["id"],
                    "name": entry["name"],
                },
            })
        if entry["emitted"]:
            for part in entry["args_parts"][entry["sent_arg_parts"]:]:
                events.append({
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": part,
                    },
                })
            entry["sent_arg_parts"] = len(entry["args_parts"])
            events.append({"type": "content_block_stop", "index": idx})

    tool_acc.clear()
    return events


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def _map_finish_reason(reason: str) -> str:
    mapping = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }
    return mapping.get(reason, "end_turn")
