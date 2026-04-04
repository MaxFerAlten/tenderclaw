"""Ollama provider — local models (Llama, Qwen, Mistral, CodeLlama, etc.).

Uses the OpenAI-compatible API that Ollama exposes at localhost:11434.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.schemas.messages import TokenUsage
from backend.services.providers.base import BaseProvider
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.providers.ollama")

OLLAMA_BASE_URL = "http://localhost:11434/v1"


class OllamaProvider(BaseProvider):
    """Provider for local Ollama models."""

    name = "ollama"
    models = ["llama", "qwen", "mistral", "codellama", "deepseek-coder", "phi", "gemma"]

    def __init__(self, base_url: str = OLLAMA_BASE_URL) -> None:
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url)

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completion from local Ollama instance."""
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            oai_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=oai_messages,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = choice.delta
                if delta and delta.content:
                    yield {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": delta.content},
                    }
                if choice.finish_reason:
                    yield {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn"},
                    }

            yield {"type": "usage", "usage": TokenUsage()}

        except Exception as exc:
            logger.error("Ollama error: %s", exc)
            raise ProviderError(
                f"Ollama error: {exc}. Is Ollama running at {OLLAMA_BASE_URL}?"
            ) from exc
