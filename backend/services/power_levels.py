"""Power-level normalization and provider adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

PowerLevel: TypeAlias = Literal["low", "medium", "high", "extra_high", "max"]
ReasoningEffort: TypeAlias = Literal["low", "medium", "high"]

POWER_LEVELS: tuple[PowerLevel, ...] = ("low", "medium", "high", "extra_high", "max")

_ALIASES: dict[str, PowerLevel] = {
    "": "medium",
    "default": "medium",
    "normal": "medium",
    "extra": "extra_high",
    "extra_high": "extra_high",
    "xhigh": "extra_high",
    "maximum": "max",
}

_GENERIC_MAX_TOKENS: dict[PowerLevel, int] = {
    "low": 4096,
    "medium": 8192,
    "high": 16384,
    "extra_high": 16384,
    "max": 16384,
}

_ANTHROPIC_THINKING_BUDGETS: dict[PowerLevel, int] = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "extra_high": 12288,
    "max": 10**9,
}

_OPENAI_REASONING_MODELS = (
    "o1",
    "o3",
    "o4",
    "gpt-5",
    "chatgpt-5",
)


@dataclass(frozen=True)
class PowerProfile:
    requested: PowerLevel
    effective: PowerLevel
    max_tokens: int
    reasoning_effort: ReasoningEffort | None = None
    anthropic_thinking_budget: int | None = None


def normalize_power_level(raw: str | None) -> PowerLevel:
    """Normalize UI/API variants into the canonical wire value."""
    if raw is None:
        return "medium"

    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if key in _ALIASES:
        return _ALIASES[key]
    if key in POWER_LEVELS:
        return cast("PowerLevel", key)
    raise ValueError(f"Unsupported power level: {raw}")


def resolve_power_profile(
    *,
    provider: str,
    model: str,
    requested: str | None,
    max_tokens: int,
) -> PowerProfile:
    """Adapt the requested power level to what the target provider supports."""
    level = normalize_power_level(requested)
    provider_key = provider.lower()
    model_key = model.lower()

    if provider_key == "anthropic" or model_key.startswith("claude"):
        budget = _anthropic_budget(level, max_tokens)
        return PowerProfile(
            requested=level,
            effective=level,
            max_tokens=max_tokens,
            anthropic_thinking_budget=budget,
        )

    if provider_key == "openai" and _supports_openai_reasoning_effort(model_key):
        effort = _to_reasoning_effort(level)
        return PowerProfile(
            requested=level,
            effective=cast("PowerLevel", effort),
            max_tokens=min(max_tokens, _GENERIC_MAX_TOKENS[level]),
            reasoning_effort=effort,
        )

    effective = _clamp_to_generic(level)
    return PowerProfile(
        requested=level,
        effective=effective,
        max_tokens=min(max_tokens, _GENERIC_MAX_TOKENS[effective]),
    )


def _anthropic_budget(level: PowerLevel, max_tokens: int) -> int | None:
    if max_tokens < 2048:
        return None
    hard_limit = max_tokens - 1024
    return max(1024, min(_ANTHROPIC_THINKING_BUDGETS[level], hard_limit))


def _supports_openai_reasoning_effort(model: str) -> bool:
    return model.startswith(_OPENAI_REASONING_MODELS)


def _to_reasoning_effort(level: PowerLevel) -> ReasoningEffort:
    if level in ("extra_high", "max"):
        return "high"
    return cast("ReasoningEffort", level)


def _clamp_to_generic(level: PowerLevel) -> PowerLevel:
    if level in ("extra_high", "max"):
        return "high"
    return level
