"""Intent Gate — classify user intent to route to the correct pipeline.

Sprint 5: after classifying Intent, the gate now also runs SkillSelector so
callers can get both the intent category and the best matching skill in one call.

Sprint 6: added IntentCache (3-turn sliding window) to stabilise intent across
turns and reduce flip-flopping. IntentGateResult now carries intent_confidence.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.services.model_router import model_router

logger = logging.getLogger("tenderclaw.orchestration.intent_gate")

# Fast/cheap model for classification — prefer a small model if available,
# fall back to whatever the router can reach.
_CLASSIFIER_MODEL = "claude-haiku-4-20250514"

_SYSTEM = """You are the TenderClaw Intent Gate.
Classify the user's coding request into ONE of these categories:
- research: understand code or search for information
- implement: write or change code
- fix: debug or repair a bug
- plan: design a new feature or architecture
- review: audit or critique existing code
- chat: general conversation not requiring code changes

Reply with ONLY the category name in lowercase."""


class Intent(str, Enum):
    RESEARCH = "research"
    IMPLEMENT = "implement"
    FIX = "fix"
    PLAN = "plan"
    REVIEW = "review"
    CHAT = "chat"


# ---------------------------------------------------------------------------
# IntentCache — 3-turn sliding window to reduce intent oscillation
# ---------------------------------------------------------------------------


@dataclass
class _IntentCacheEntry:
    intent: Intent
    prompt_snippet: str  # first 60 chars for debug


class IntentCache:
    """Sliding-window cache for intent classification.

    Keeps the last ``WINDOW`` turns. If a majority (≥ 2 of 3) agree on an
    intent, the gate can return the cached result instead of calling the
    classifier again, which avoids flip-flopping on borderline prompts.
    """

    WINDOW: int = 3

    def __init__(self, session_id: str = "") -> None:
        self.session_id = session_id
        self._entries: deque[_IntentCacheEntry] = deque(maxlen=self.WINDOW)

    def push(self, intent: Intent, prompt: str) -> None:
        """Record a new classification result."""
        self._entries.append(_IntentCacheEntry(intent=intent, prompt_snippet=prompt[:60]))

    def majority_intent(self) -> Intent | None:
        """Return the intent that appears ≥ 2 times in the window, or None."""
        if len(self._entries) < 2:
            return None
        counts: dict[Intent, int] = {}
        for entry in self._entries:
            counts[entry.intent] = counts.get(entry.intent, 0) + 1
        for intent, count in counts.items():
            if count >= 2:
                return intent
        return None

    def confidence(self) -> float:
        """Confidence based on window agreement (0.0–1.0)."""
        if not self._entries:
            return 0.5
        majority = self.majority_intent()
        if majority is None:
            return round(1.0 / len(self._entries), 2)
        count = sum(1 for e in self._entries if e.intent == majority)
        return round(count / len(self._entries), 2)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


# Module-level cache store keyed by session_id
_session_caches: dict[str, IntentCache] = {}


def get_intent_cache(session_id: str = "") -> IntentCache:
    """Return (or create) the IntentCache for a session."""
    if session_id not in _session_caches:
        _session_caches[session_id] = IntentCache(session_id=session_id)
    return _session_caches[session_id]


def clear_intent_cache(session_id: str = "") -> None:
    """Clear the cache for a session (call on session reset)."""
    if session_id in _session_caches:
        _session_caches[session_id].clear()


async def classify_intent(prompt: str, session_model: str = "") -> Intent:
    """Classify user prompt into an Intent using a fast model.

    Uses the cheapest available provider. Skips if no cloud key is configured.
    """
    from backend.config import settings
    from backend.api.config import _global_config

    # Pick classifier model based on available keys (check global config first)
    if settings.anthropic_api_key or _global_config.get("anthropic_api_key"):
        classifier_model = "claude-haiku-4-20250514"
    elif settings.openai_api_key or _global_config.get("openai_api_key"):
        classifier_model = "gpt-4o-mini"
    elif settings.openrouter_api_key or _global_config.get("openrouter_api_key"):
        classifier_model = "openai/gpt-4o-mini"
    else:
        # Local-only setup — skip classification entirely
        return Intent.IMPLEMENT

    try:
        result = await model_router.generate_message(
            model=classifier_model,
            messages=[{"role": "user", "content": prompt}],
            system=_SYSTEM,
        )
        prediction = result.content.strip().lower()
        if prediction in Intent._value2member_map_:
            return Intent(prediction)
    except Exception as exc:
        logger.warning("Intent classification failed (%s), defaulting to implement", exc)

    return Intent.IMPLEMENT


# ---------------------------------------------------------------------------
# IntentGateResult — intent + skill selection + confidence in one call
# ---------------------------------------------------------------------------


@dataclass
class IntentGateResult:
    """Combined output of intent classification + skill selection.

    Attributes:
        intent:            Classified intent category.
        skill_name:        Name of the auto-selected skill, or empty string.
        confidence:        Skill-selection confidence (0–1).
        reason:            Skill-selection rationale.
        intent_confidence: How stable the intent is across recent turns (0–1).
                           1.0 = unanimous window, 0.5 = first turn / mixed.
    """

    intent: Intent
    skill_name: str = ""
    confidence: float = 0.0
    reason: str = ""
    intent_confidence: float = 0.5

    @property
    def has_skill(self) -> bool:
        return bool(self.skill_name)


async def classify_intent_with_skill(
    prompt: str,
    *,
    risk: str = "medium",
    session_model: str = "",
    session_id: str = "",
    use_cache: bool = True,
) -> IntentGateResult:
    """Classify intent AND auto-select a skill in one call.

    The intent drives the ``phase`` argument to :func:`SkillSelector.select`,
    so the skill selection is grounded in the classified intent.

    Sprint 6: uses a 3-turn sliding window cache to stabilise intent across
    consecutive turns. If the window shows a clear majority intent, that intent
    is returned directly without an additional classifier call, cutting latency
    and preventing flip-flopping on ambiguous prompts.

    Args:
        prompt:     User's message.
        risk:       Risk level forwarded to SkillSelector.
        session_model: Optional model override.
        session_id: Session key for the IntentCache (empty = shared cache).
        use_cache:  Set False to always call the classifier (useful in tests).

    Returns an :class:`IntentGateResult` with all fields populated.
    """
    from backend.core.skills import skill_selector

    cache = get_intent_cache(session_id) if use_cache else IntentCache()

    # Try to short-circuit via cache majority
    cached_majority = cache.majority_intent() if use_cache else None
    if cached_majority is not None:
        intent = cached_majority
        intent_conf = cache.confidence()
        logger.debug("IntentGate: cache hit session=%r intent=%s conf=%.2f", session_id, intent.value, intent_conf)
    else:
        intent = await classify_intent(prompt, session_model=session_model)
        cache.push(intent, prompt)
        intent_conf = cache.confidence()

    phase = intent.value  # Intent values match phase names used by SkillSelector
    match = skill_selector.select(prompt, phase=phase, risk=risk)

    logger.info(
        "IntentGate: intent=%s intent_conf=%.2f skill=%s skill_conf=%.2f",
        intent.value, intent_conf, match.skill_name or "(none)", match.confidence,
    )
    return IntentGateResult(
        intent=intent,
        skill_name=match.skill_name,
        confidence=match.confidence,
        reason=match.reason,
        intent_confidence=intent_conf,
    )
