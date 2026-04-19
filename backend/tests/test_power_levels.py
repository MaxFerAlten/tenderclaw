from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, ClassVar, get_type_hints

import pytest
from pydantic import ValidationError

from backend.core.conversation import run_conversation_turn
from backend.schemas.ws import WSUserMessage
from backend.services import model_router as model_router_module
from backend.services.model_router import ModelRouter
from backend.services.power_levels import (
    PowerLevel,
    PowerProfile,
    normalize_power_level,
    resolve_power_profile,
)
from backend.services.providers.base import BaseProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def test_ws_user_message_accepts_all_power_levels() -> None:
    for level in ("low", "medium", "high", "extra_high", "max"):
        msg = WSUserMessage.model_validate(
            {"type": "user_message", "content": "ciao", "power_level": level}
        )
        assert msg.power_level == level


def test_ws_user_message_rejects_unknown_power_level() -> None:
    with pytest.raises(ValidationError):
        WSUserMessage.model_validate(
            {"type": "user_message", "content": "ciao", "power_level": "ultra"}
        )


def test_normalize_power_level_accepts_ui_aliases() -> None:
    assert normalize_power_level("extra high") == "extra_high"
    assert normalize_power_level("extra-high") == "extra_high"
    assert normalize_power_level("xhigh") == "extra_high"
    assert normalize_power_level("maximum") == "max"
    assert normalize_power_level(None) == "medium"


def test_claude_supports_all_power_levels_with_thinking_budget() -> None:
    profile = resolve_power_profile(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        requested="max",
        max_tokens=16384,
    )

    assert profile.requested == "max"
    assert profile.effective == "max"
    assert profile.anthropic_thinking_budget == 15360
    assert profile.max_tokens == 16384


def test_openai_like_models_clamp_extra_levels_to_high() -> None:
    profile = resolve_power_profile(
        provider="openai",
        model="gpt-5.4",
        requested="extra_high",
        max_tokens=16384,
    )

    assert profile.requested == "extra_high"
    assert profile.effective == "high"
    assert profile.reasoning_effort == "high"


def test_generic_models_adapt_without_reasoning_parameters() -> None:
    profile = resolve_power_profile(
        provider="lmstudio",
        model="local-model",
        requested="max",
        max_tokens=16384,
    )

    assert profile.effective == "high"
    assert profile.reasoning_effort is None
    assert profile.anthropic_thinking_budget is None
    assert profile.max_tokens == 16384


def test_conversation_turn_accepts_power_level_keyword() -> None:
    signature = inspect.signature(run_conversation_turn)

    power_param = signature.parameters["power_level"]
    assert power_param.default == "medium"
    assert get_type_hints(run_conversation_turn)["power_level"] == PowerLevel


class _FakeProvider(BaseProvider):
    name = "fake"
    models: ClassVar[list[str]] = ["fake"]

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
        power_profile: PowerProfile | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "power_profile": power_profile,
            }
        )
        yield {"type": "usage", "usage": {}}


@pytest.mark.asyncio
async def test_model_router_passes_adapted_power_profile_to_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeProvider()
    router = ModelRouter()

    async def fake_resolve_provider(model: str, config: dict[str, Any] | None = None) -> str:
        return "openai"

    monkeypatch.setattr(model_router_module, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(router, "_get_provider", lambda _name, _config=None: provider)

    events = [
        event
        async for event in router.stream_message(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "ciao"}],
            power_level="max",
        )
    ]

    assert events == [{"type": "usage", "usage": {}}]
    assert len(provider.calls) == 1
    profile = provider.calls[0]["power_profile"]
    assert isinstance(profile, PowerProfile)
    assert profile.requested == "max"
    assert profile.effective == "high"
    assert profile.reasoning_effort == "high"
