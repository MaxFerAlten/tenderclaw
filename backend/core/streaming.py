"""Streaming helpers — parse model_router events into structured data."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable

from backend.schemas.messages import TextBlock, TokenUsage, ToolUseBlock
from backend.schemas.ws import (
    WSAssistantText,
    WSAssistantThinking,
    WSToolUseStart,
    WSInputJsonDelta,
)

logger = logging.getLogger("tenderclaw.core.streaming")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]

_HIDDEN_THOUGHT_START_RE = re.compile(
    r"<\s*(?:antThinking|thinking|think|analysis|scratchpad)\b[^>]*>",
    re.IGNORECASE,
)
_HIDDEN_THOUGHT_END_RE = re.compile(
    r"</\s*(?:antThinking|thinking|think|analysis|scratchpad)\s*>",
    re.IGNORECASE,
)
_HIDDEN_THOUGHT_TAIL_CHARS = 128


class StreamCollector:
    """Collects streaming events from model_router into structured results."""

    def __init__(self, message_id: str, send: SendFn) -> None:
        self.message_id = message_id
        self.send = send
        self.text_parts: list[str] = []
        self.tool_uses: list[ToolUseBlock] = []
        self.stop_reason: str = "end_turn"
        self.usage: TokenUsage = TokenUsage()
        self._tool_blocks: dict[int, dict[str, str]] = {}
        self._hidden_thought_filter = HiddenThoughtFilter()

    async def process(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "")

        if event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                index = _event_index(event)
                self._tool_blocks[index] = {
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "json": "",
                }
                await self.send(WSToolUseStart(
                    tool_use_id=self._tool_blocks[index]["id"],
                    tool_name=self._tool_blocks[index]["name"],
                    message_id=self.message_id,
                ).model_dump())

        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            dtype = delta.get("type", "")

            if dtype == "text_delta":
                await self._emit_text(self._hidden_thought_filter.feed(delta.get("text", "")))

            elif dtype == "thinking_delta":
                await self.send(WSAssistantThinking(
                    delta=delta.get("thinking", ""),
                    message_id=self.message_id,
                ).model_dump())

            elif dtype == "input_json_delta":
                index = _event_index(event)
                state = self._tool_blocks.setdefault(index, {"id": "", "name": "", "json": ""})
                partial = delta.get("partial_json", "")
                state["json"] += partial
                if partial:
                    await self.send(WSInputJsonDelta(
                        tool_use_id=state["id"],
                        partial_json=partial,
                    ).model_dump())

        elif event_type == "content_block_stop":
            if "index" in event:
                self._finish_tool_block(_event_index(event))
            else:
                for index in sorted(self._tool_blocks):
                    self._finish_tool_block(index)

        elif event_type == "message_delta":
            await self._flush_text_filter()
            self.stop_reason = event.get("delta", {}).get("stop_reason", "end_turn") or "end_turn"

        elif event_type == "usage":
            await self._flush_text_filter()
            raw = event.get("usage", {})
            if isinstance(raw, TokenUsage):
                self.usage = raw
            elif isinstance(raw, dict):
                self.usage = TokenUsage(
                    input_tokens=raw.get("input_tokens", 0),
                    output_tokens=raw.get("output_tokens", 0),
                )

    def content_blocks(self) -> list[TextBlock | ToolUseBlock]:
        blocks: list[TextBlock | ToolUseBlock] = []
        if self.text_parts:
            blocks.append(TextBlock(text="".join(self.text_parts)))
        blocks.extend(self.tool_uses)
        return blocks

    async def _emit_text(self, text: str) -> None:
        if not text:
            return
        self.text_parts.append(text)
        await self.send(WSAssistantText(delta=text, message_id=self.message_id).model_dump())

    async def _flush_text_filter(self) -> None:
        await self._emit_text(self._hidden_thought_filter.flush())

    def _finish_tool_block(self, index: int) -> None:
        state = self._tool_blocks.pop(index, None)
        if not state or not state["id"]:
            return
        try:
            parsed = json.loads(state["json"]) if state["json"] else {}
        except json.JSONDecodeError:
            parsed = {}
        self.tool_uses.append(ToolUseBlock(
            id=state["id"],
            name=state["name"],
            input=parsed,
        ))


def _event_index(event: dict[str, Any]) -> int:
    raw = event.get("index", 0)
    return raw if isinstance(raw, int) else 0


class HiddenThoughtFilter:
    """Removes model-emitted hidden-thinking tags from visible streamed text."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_hidden = False

    def feed(self, text: str) -> str:
        if not text:
            return ""
        self._buffer += text
        return self._drain(final=False)

    def flush(self) -> str:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        visible: list[str] = []

        while self._buffer:
            if self._inside_hidden:
                end = _HIDDEN_THOUGHT_END_RE.search(self._buffer)
                if not end:
                    if final:
                        self._buffer = ""
                    else:
                        self._buffer = self._buffer[-_HIDDEN_THOUGHT_TAIL_CHARS:]
                    break
                self._buffer = self._buffer[end.end():]
                self._inside_hidden = False
                continue

            start = _HIDDEN_THOUGHT_START_RE.search(self._buffer)
            if start:
                visible.append(self._buffer[:start.start()])
                self._buffer = self._buffer[start.end():]
                self._inside_hidden = True
                continue

            if final:
                visible.append(self._buffer)
                self._buffer = ""
            elif len(self._buffer) > _HIDDEN_THOUGHT_TAIL_CHARS:
                visible.append(self._buffer[:-_HIDDEN_THOUGHT_TAIL_CHARS])
                self._buffer = self._buffer[-_HIDDEN_THOUGHT_TAIL_CHARS:]
            break

        return "".join(visible)
