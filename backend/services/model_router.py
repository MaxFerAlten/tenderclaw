"""Model router — route requests to the correct AI provider.

Multi-model from day 1: Claude, GPT, Gemini, Grok, DeepSeek, Ollama, LM Studio, OpenRouter.
Providers are lazy-initialized on first use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from backend.services.providers.base import BaseProvider
from backend.utils.errors import ProviderError

logger = logging.getLogger("tenderclaw.services.model_router")


@dataclass
class GenerateResult:
    content: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


# Model name prefix -> provider name
# Order matters: more specific prefixes first
PROVIDER_MAP: dict[str, str] = {
    # OpenCode specific (most specific first)
    "qwen3.6-plus-free": "opencode",
    "minimax-m2.5-free": "opencode",
    "nemotron-3-super-free": "opencode",
    "trinity-large-preview-free": "opencode",
    "big-pickle": "opencode",
    "opencode": "opencode",
    # Other providers
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "chatgpt": "openai",
    "gemini": "google",
    "grok": "xai",
    "deepseek": "openrouter",
    "lmstudio": "lmstudio",
    "lm-studio": "lmstudio",
    "mistral": "ollama",
    "codellama": "ollama",
    "phi": "ollama",
    "qwen": "ollama",
    "gemma": "lmstudio",
    "llama": "ollama",
    "openrouter": "openrouter",
}


def detect_provider(model: str) -> str:
    """Detect the provider from a model name."""
    model_lower = model.lower()
    
    # Check if model has a slash (namespaced format)
    if "/" in model:
        # Check known OpenRouter prefixes first
        openrouter_prefixes = (
            "anthropic/", "openai/", "google/", "mistral/", "meta-llama/", 
            "mistralai/", "NousResearch/", "teknium/", "deepseek/", "xai/", 
            "amazon/", "qwen/", "nvidia/", "liuunot/", "nousresearch/",
            "cognitivecomputations/", "meta/", "llama/", "openchat/"
        )
        if any(model_lower.startswith(p) for p in openrouter_prefixes):
            return "openrouter"
        
        # Check OpenCode prefixes
        opencode_prefixes = ("opencode/",)
        if any(model_lower.startswith(p) for p in opencode_prefixes):
            return "opencode"
        
        # Unknown namespaced model - try LM Studio
        import urllib.request
        from backend.config import settings
        
        for endpoint in ["/v1/models", "/api/v1/models"]:
            url = settings.lmstudio_base_url.rstrip("/") + endpoint
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        import json
                        data = json.loads(resp.read().decode())
                        if "data" in data:
                            model_ids = [m.get("id", "").lower() for m in data.get("data", [])]
                        elif "models" in data:
                            model_ids = [m.get("id", "").lower() for m in data.get("models", [])]
                        else:
                            model_ids = []
                        if any(model_lower in mId for mId in model_ids):
                            return "lmstudio"
            except Exception as exc:
                logger.debug("LM Studio model check failed for %s: %s", endpoint, exc)

        return "lmstudio"
    
    # No slash - check LM Studio FIRST if available
    import urllib.request
    from backend.config import settings
    
    lmstudio_available = False
    lmstudio_models = []
    
    for endpoint in ["/v1/models", "/api/v1/models"]:
        url = settings.lmstudio_base_url.rstrip("/") + endpoint
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    import json
                    data = json.loads(resp.read().decode())
                    if "data" in data:
                        models = [m.get("id", "").lower() for m in data.get("data", [])]
                    elif "models" in data:
                        models = [m.get("id", "").lower() for m in data.get("models", [])]
                    else:
                        models = []
                    
                    lmstudio_models.extend(models)
                    lmstudio_available = True
        except Exception as exc:
            logger.debug("LM Studio availability check failed for %s: %s", endpoint, exc)
    
    if lmstudio_available and lmstudio_models:
        # Check PROVIDER_MAP first — explicit mappings take priority over LM Studio
        for prefix, provider in PROVIDER_MAP.items():
            if prefix in model_lower:
                return provider
        # Check if model name is in LM Studio's available models
        if any(model_lower in mId for mId in lmstudio_models):
            return "lmstudio"
    
    # Check PROVIDER_MAP before defaulting to lmstudio
    for prefix, provider in PROVIDER_MAP.items():
        if prefix in model_lower:
            return provider
    
    # If LM Studio was checked but model not found, check if any partial match
    if lmstudio_available:
        for mId in lmstudio_models:
            if model_lower in mId or mId in model_lower:
                return "lmstudio"
        return "lmstudio"
    
    return "anthropic"


class ModelRouter:
    """Routes model requests to the correct AI provider client."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def list_providers(self) -> list[str]:
        """List all available provider names."""
        return ["anthropic", "openai", "google", "xai", "deepseek", "ollama", "lmstudio", "openrouter", "opencode"]

    def _get_provider(self, name: str, config: dict[str, Any] | None = None) -> BaseProvider:
        """Lazy-init a provider by name."""
        # For Ollama/LM Studio/OpenRouter/OpenCode, always recreate to use new URL/key
        if name in ("ollama", "lmstudio", "openrouter", "opencode"):
            logger.info(f"_get_provider: creating fresh provider for {name}")
            provider = _create_provider(name, config)
            self._providers[name] = provider
            return provider
        
        if name in self._providers:
            return self._providers[name]

        provider = _create_provider(name, config)
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
        config: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Route a streaming message request to the appropriate provider."""
        provider_name = detect_provider(model)
        provider = self._get_provider(provider_name, config)

        try:
            async for event in provider.stream(
                model=model,
                messages=messages,
                system=system,
                tools=tools,
                max_tokens=max_tokens,
            ):
                yield event
        except ProviderError as exc:
            # No automatic fallback - propagate error to user
            logger.error("%s provider failed: %s", provider_name, exc)
            raise

    async def generate_message(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
        config: dict[str, Any] | None = None,
    ) -> GenerateResult:
        """Non-streaming generate — collect all deltas into a result."""
        content_parts: list[str] = []
        usage: dict[str, Any] = {}

        async for event in self.stream_message(
            model=model,
            messages=messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
            config=config,
        ):
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    content_parts.append(delta.get("text", ""))
            elif event.get("type") == "usage":
                usage = event.get("usage", {})

        return GenerateResult(content="".join(content_parts), usage=usage)


def _create_provider(name: str, config: dict[str, Any] | None = None) -> BaseProvider:
    """Create a provider instance by name."""
    if name == "anthropic":
        from backend.services.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from backend.services.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "google":
        from backend.services.providers.google_provider import GoogleProvider
        return GoogleProvider()
    if name == "deepseek":
        # Route deepseek to OpenRouter
        from backend.services.providers.openrouter_provider import OpenRouterProvider
        from backend.services.session_store import session_store
        from backend.utils.errors import SessionNotFoundError
        from backend.api.config import _global_config

        key = None
        if config:
            key = config.get("openrouter_api_key")
        if not key and config and "session_id" in config:
            try:
                session = session_store.get(config["session_id"])
                key = session.get_api_key("openrouter")
            except SessionNotFoundError:
                pass
        if not key:
            key = _global_config.get("openrouter_api_key")
        if not key:
            from backend.config import settings
            key = settings.openrouter_api_key
        
        logger.info(f"_create_provider(openrouter): key from config='{str(key)[:20]}...'")
        return OpenRouterProvider(api_key=key)
    if name == "openrouter":
        from backend.services.providers.openrouter_provider import OpenRouterProvider
        from backend.services.session_store import session_store
        from backend.utils.errors import SessionNotFoundError
        from backend.api.config import _global_config

        key = None
        if config:
            key = config.get("openrouter_api_key")
        if not key and config and "session_id" in config:
            try:
                session = session_store.get(config["session_id"])
                key = session.get_api_key("openrouter")
            except SessionNotFoundError:
                pass
        if not key:
            key = _global_config.get("openrouter_api_key")
        if not key:
            from backend.config import settings
            key = settings.openrouter_api_key
        
        logger.info(f"_create_provider(openrouter): key from config='{str(key)[:20]}...'")
        return OpenRouterProvider(api_key=key)
    if name == "xai":
        from backend.services.providers.xai_provider import XAIProvider
        return XAIProvider()
    if name == "ollama":
        from backend.services.providers.ollama_provider import OllamaProvider
        url = config.get("ollama_url") if config else None
        return OllamaProvider(base_url=url)
    if name == "lmstudio":
        from backend.services.providers.lmstudio_provider import LMStudioProvider
        url = config.get("lmstudio_url") if config else None
        return LMStudioProvider(base_url=url)
    if name == "opencode":
        from backend.services.providers.opencode_provider import OpenCodeProvider
        from backend.api.config import _global_config
        
        key = None
        if config:
            key = config.get("opencode_api_key")
        if not key:
            key = _global_config.get("opencode_api_key")
        if not key:
            from backend.config import settings
            key = settings.opencode_api_key
        return OpenCodeProvider(api_key=key)

    raise ProviderError(f"Unknown provider: {name}")


# Module-level instance
model_router = ModelRouter()
