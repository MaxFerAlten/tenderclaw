"""Intent Gate — classify user intent to route to the correct pipeline.

Analyzes the prompt to determine if it's research, implementation,
bug fixing, or planning.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from backend.services.model_router import model_router

logger = logging.getLogger("tenderclaw.orchestration.intent_gate")


class Intent(str, Enum):
    """Broad categories for user requests."""

    RESEARCH = "research"      # Explore codebase or web
    IMPLEMENT = "implement"    # Write feature code
    FIX = "fix"                # Debug and repair
    PLAN = "plan"              # Design/Architect
    REVIEW = "review"          # Critique/Audit
    CHAT = "chat"              # General interaction


async def classify_intent(prompt: str) -> Intent:
    """Classify user's prompt into a specific Intent."""
    system = """You are the **TenderClaw Intent Gate**.
Your job is to classify the user's coding request into ONE category:
- **research**: The user wants to understand code or search for information.
- **implement**: The user wants you to write or change code.
- **fix**: The user has an error or bug that needs fixing.
- **plan**: The user wants to design a new feature or architect a project.
- **review**: The user wants an audit or critique of existing code.
- **chat**: General conversation or questions not requiring code changes.

Return ONLY the single category name in lowercase. No explanation."""

    messages = [{"role": "user", "content": prompt}]
    
    try:
        response = await model_router.generate_message(
            model="gpt-4o-mini", # Use a fast/cheap model for classification
            messages=messages,
            system=system,
        )
        prediction = response.content.strip().lower()
        if prediction in [i.value for i in Intent]:
            return Intent(prediction)
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)

    return Intent.IMPLEMENT # Default to implementation
