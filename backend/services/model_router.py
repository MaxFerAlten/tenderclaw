"""Model router — route requests to the correct AI provider.

Multi-model from day 1: Claude, GPT, Gemini, Grok, DeepSeek, Ollama.
Providers are lazy-initialized on first use to avoid startup failures
when API keys are missing for unused providers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from backend.services.providers.base import BaseProvider
from backend.utils.errors import ProviderError


@dataclass
class GenerateResult:
    """Non-streaming response collected from a provider stream."""
    content: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

logger = logging.getLogger("tenderclaw.services.model_router")

# Model name prefix -> provider name
PROVIDER_MAP: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "chatgpt": "openai",
    "gemini": "google",
    "grok": "xai",
    "deepseek": "deepseek",
    "llama": "ollama",
    "qwen": "ollama",
    "mistral": "ollama",
    "codellama": "ollama",
    "phi": "ollama",
    "gemma": "ollama",
}


def detect_provider(model: str) -> str:
    """Detect the provider from a model name."""
    model_lower = model.lower()
    for prefix, provider in PROVIDER_MAP.items():
        if prefix in model_lower:
            return provider
    return "anthropic"


class ModelRouter:
    """Routes model requests to the correct provider client."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def _get_provider(self, name: str) -> BaseProvider:
        """Lazy-init a provider by name."""
        if name in self._providers:
            return self._providers[name]

        provider = _create_provider(name)
        self._providers[name] = provider
        logger.info("Provider initialized: %s", name)
        return provider

    async def stream_message(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> AsyncIterator[dict[str, Any]]:
        """Route a streaming message request to the appropriate provider."""
        provider_name = detect_provider(model)
        provider = self._get_provider(provider_name)

        async for event in provider.stream(
            model=model,
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
        ):
            yield event

    async def generate_message(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> GenerateResult:
        """Non-streaming convenience: collect full response as a single string."""
        parts: list[str] = []
        usage_info: dict[str, Any] = {}

        async for event in self.stream_message(
            model=model,
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
        ):
            evt_type = event.get("type", "")
            if evt_type == "content_block_delta":
                text = event.get("delta", {}).get("text", "")
                if text:
                    parts.append(text)
            elif evt_type == "message_delta" and "usage" in event:
                usage_info = event["usage"]

        return GenerateResult(content="".join(parts), usage=usage_info)

    def list_providers(self) -> list[str]:
        """List all available provider names."""
        return list(PROVIDER_MAP.values())


def _create_provider(name: str) -> BaseProvider:
    """Factory function — create a provider instance by name."""
    if name == "anthropic":
        from backend.services.anthropic_client import AnthropicClient
        return AnthropicClient()
    if name == "openai":
        from backend.services.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "google":
        from backend.services.providers.google_provider import GoogleProvider
        return GoogleProvider()
    if name == "deepseek":
        from backend.services.providers.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider()
    if name == "xai":
        from backend.services.providers.xai_provider import XAIProvider
        return XAIProvider()
    if name == "ollama":
        from backend.services.providers.ollama_provider import OllamaProvider
        return OllamaProvider()

    raise ProviderError(f"Unknown provider: {name}")


# Module-level instance
model_router = ModelRouter()
