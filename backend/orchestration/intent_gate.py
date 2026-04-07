"""Intent Gate — classify user intent to route to the correct pipeline."""

from __future__ import annotations

import logging
from enum import Enum

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
