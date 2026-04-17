"""RoleRouter — decide which agent executes a task and at which tier/posture.

Replaces implicit routing scattered across the pipeline with one explicit
decision surface that exposes *why* a given agent was chosen (reason field).

Usage::

    from backend.services.role_router import role_router, RoleRouterResult

    result: RoleRouterResult = role_router.route("write unit tests for auth.py")
    # result.agent = "sisyphus", result.tier = AgentTier.STANDARD, ...
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("tenderclaw.services.role_router")


# ---------------------------------------------------------------------------
# Domain enums
# ---------------------------------------------------------------------------


class AgentTier(str, Enum):
    """Capability / cost tier of the agent model to use."""
    LIGHTWEIGHT = "lightweight"   # fast, cheap — haiku-class
    STANDARD = "standard"         # balanced — sonnet-class
    FLAGSHIP = "flagship"         # max capability — opus-class


class AgentPosture(str, Enum):
    """Behavioural posture: how freely the agent should act."""
    CONSERVATIVE = "conservative"  # ask before any side-effect
    BALANCED = "balanced"          # act within safe scope, confirm risky ops
    AGGRESSIVE = "aggressive"      # proceed autonomously, minimise interruptions


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class RoleRouterResult(BaseModel):
    """The outcome of a routing decision."""

    agent: str                        # agent registry name, e.g. "sisyphus"
    tier: AgentTier = AgentTier.STANDARD
    posture: AgentPosture = AgentPosture.BALANCED
    confidence: float = 1.0           # 0.0–1.0 — how certain the router is
    reason: str = ""                  # human-readable routing rationale
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------

# Each rule: (pattern, agent, tier, posture, confidence, reason)
_RULES: list[tuple[re.Pattern, str, AgentTier, AgentPosture, float, str]] = [
    # Research / investigation tasks → oracle, lightweight, conservative
    (
        re.compile(r"\b(research|investigate|find out|look up|search for|analyse|summarize|explain)\b", re.I),
        "oracle", AgentTier.LIGHTWEIGHT, AgentPosture.CONSERVATIVE, 0.85,
        "read-only investigation task → oracle (lightweight, conservative)",
    ),
    # Architecture / planning / design → metis, flagship, conservative
    (
        re.compile(r"\b(architect|design|plan|spec|blueprint|evaluate|compare|decide|strategy)\b", re.I),
        "metis", AgentTier.FLAGSHIP, AgentPosture.CONSERVATIVE, 0.9,
        "design/planning task → metis (flagship, conservative)",
    ),
    # Testing → sisyphus standard balanced (test writing is low-risk execution)
    (
        re.compile(r"\b(test|pytest|unittest|coverage|spec|fixture)\b", re.I),
        "sisyphus", AgentTier.STANDARD, AgentPosture.BALANCED, 0.8,
        "testing task → sisyphus (standard, balanced)",
    ),
    # Security / audit / review → sentinel, flagship, conservative
    (
        re.compile(r"\b(security|audit|review|vulnerabilit|pentest|compliance|scan)\b", re.I),
        "sentinel", AgentTier.FLAGSHIP, AgentPosture.CONSERVATIVE, 0.92,
        "security/audit task → sentinel (flagship, conservative)",
    ),
    # Debugging / fixing → fixer, standard, aggressive
    (
        re.compile(r"\b(fix|debug|repair|patch|broken|error|traceback|exception|bug)\b", re.I),
        "fixer", AgentTier.STANDARD, AgentPosture.AGGRESSIVE, 0.85,
        "fix/debug task → fixer (standard, aggressive)",
    ),
    # Verification / QA → momus, lightweight, conservative
    (
        re.compile(r"\b(verify|validate|check|assert|confirm|qa|quality)\b", re.I),
        "momus", AgentTier.LIGHTWEIGHT, AgentPosture.CONSERVATIVE, 0.8,
        "verification task → momus (lightweight, conservative)",
    ),
    # Heavy execution / build / deploy → sisyphus, flagship, aggressive
    (
        re.compile(r"\b(implement|build|create|generate|refactor|migrate|deploy|scaffold)\b", re.I),
        "sisyphus", AgentTier.FLAGSHIP, AgentPosture.AGGRESSIVE, 0.75,
        "heavy implementation task → sisyphus (flagship, aggressive)",
    ),
]

_DEFAULT = RoleRouterResult(
    agent="sisyphus",
    tier=AgentTier.STANDARD,
    posture=AgentPosture.BALANCED,
    confidence=0.5,
    reason="no specific pattern matched — default to sisyphus (standard, balanced)",
)


# ---------------------------------------------------------------------------
# RoleRouter
# ---------------------------------------------------------------------------


class RoleRouter:
    """Stateless router that maps task descriptions to agent routing decisions."""

    def route(
        self,
        task: str,
        *,
        context: dict[str, Any] | None = None,
        force_agent: str | None = None,
        force_tier: AgentTier | None = None,
        force_posture: AgentPosture | None = None,
    ) -> RoleRouterResult:
        """Produce a routing decision for *task*.

        Args:
            task:           Natural-language task description.
            context:        Optional dict with extra context (session_id, pipeline_stage, etc.).
            force_agent:    Override the routed agent unconditionally.
            force_tier:     Override the tier unconditionally.
            force_posture:  Override the posture unconditionally.

        Returns:
            A :class:`RoleRouterResult` with the selected agent, tier, posture,
            confidence, and human-readable reason.
        """
        result = self._match(task)

        # Apply any forced overrides
        if force_agent:
            result = result.model_copy(update={"agent": force_agent, "reason": f"forced agent={force_agent}; " + result.reason})
        if force_tier:
            result = result.model_copy(update={"tier": force_tier})
        if force_posture:
            result = result.model_copy(update={"posture": force_posture})

        if context:
            result = result.model_copy(update={"metadata": {**result.metadata, **context}})

        logger.info(
            "RoleRouter: task=%r → agent=%s tier=%s posture=%s confidence=%.2f",
            task[:80],
            result.agent,
            result.tier.value,
            result.posture.value,
            result.confidence,
        )
        return result

    def route_by_keywords(self, text: str) -> RoleRouterResult:
        """Route using only keyword matching — convenience alias for ``route()``."""
        return self.route(text)

    def _match(self, task: str) -> RoleRouterResult:
        """Find the first matching rule or return the default."""
        for pattern, agent, tier, posture, confidence, reason in _RULES:
            if pattern.search(task):
                return RoleRouterResult(
                    agent=agent,
                    tier=tier,
                    posture=posture,
                    confidence=confidence,
                    reason=reason,
                )
        return _DEFAULT.model_copy()

    def explain(self, task: str) -> list[dict[str, Any]]:
        """Return all matching rules for *task* — useful for debugging."""
        matches = []
        for pattern, agent, tier, posture, confidence, reason in _RULES:
            if pattern.search(task):
                matches.append({
                    "agent": agent,
                    "tier": tier.value,
                    "posture": posture.value,
                    "confidence": confidence,
                    "reason": reason,
                    "pattern": pattern.pattern,
                })
        return matches


# Module-level singleton
role_router = RoleRouter()
