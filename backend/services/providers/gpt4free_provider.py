"""gpt4free provider — free OpenAI-compatible API endpoints.

Uses the OpenAI-compatible API that gpt4free servers expose.
"""

from __future__ import annotations

import logging
import urllib.request as _urlreq
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.config import settings
from backend.schemas.messages import TokenUsage
from backend.services.providers.base import BaseProvider
from backend.services.power_levels import PowerProfile
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.providers.gpt4free")


class Gpt4FreeProvider(BaseProvider):
    """Provider for gpt4free (free OpenAI-compatible endpoints)."""

    name = "gpt4free"
    models = ["gpt4free"]

    def __init__(self, base_url: str | None = None) -> None:
        url = base_url or settings.gpt4free_base_url
        base = url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self._base_url = base + "/v1"
        self._healthy = False
        try:
            probe = self._base_url + "/models"
            with _urlreq.urlopen(probe, timeout=3) as resp:
                if resp.status == 200:
                    self._healthy = True
        except Exception:
            self._healthy = False
        self._client = AsyncOpenAI(api_key="gpt4free", base_url=self._base_url)
        logger.info("gpt4free provider initialized with base_url: %s", self._base_url)

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
        power_profile: PowerProfile | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completion from gpt4free server."""
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            oai_messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

        if not getattr(self, "_healthy", True):
            raise ProviderError(f"gpt4free not healthy or not reachable at {self._base_url}")

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
                content = delta.content if delta else ""

                if content:
                    yield {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content},
                    }
                if choice.finish_reason:
                    yield {
                        "type": "message_delta",
                        "delta": {"stop_reason": choice.finish_reason},
                    }

            yield {"type": "usage", "usage": TokenUsage()}

        except Exception as exc:
            logger.error("gpt4free error: %s", exc)
            raise ProviderError(
                f"gpt4free error: {exc}. Is the gpt4free server running at {settings.gpt4free_base_url}?"
            ) from exc
