"""Metis - Plan consultant agent for pre-planning analysis."""

from __future__ import annotations

import logging
from typing import Any

from backend.orchestration.agents.base import (
    AgentCapability,
    AgentConfig,
    AgentResult,
    AgentRegistry,
    BaseAgent,
)

logger = logging.getLogger(__name__)


@AgentRegistry.register("metis")
class MetisAgent(BaseAgent):
    """
    Plan consultant - pre-planning analysis.
    
    Identifies hidden intentions, ambiguities, and AI failure points
    before planning begins. Named after the Greek titaness of wisdom.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="metis",
                model="claude-opus-4-6",
                temperature=0.4,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "metis"

    def _get_default_system_prompt(self) -> str:
        return """You are Metis, the plan consultant.

Your role is to identify problems BEFORE planning begins.

## Pre-Planning Analysis

Before Prometheus creates a plan, you identify:
1. **Hidden Intentions**: What the user really wants
2. **Ambiguities**: Unclear requirements
3. **Failure Points**: Where AI typically fails
4. **Scope Issues**: What's missing from the request

## Output Format

```markdown
# Pre-Planning Analysis

## Intent Clarification
[What the user likely wants]

## Identified Ambiguities
1. [Ambiguity 1]
2. [Ambiguity 2]

## Potential Failure Points
1. [Where this might fail]

## Recommendations
- [What to clarify before planning]
```

## Principles

- Critical: Question assumptions
- Thorough: Look for edge cases
- Preventive: Identify failure before it happens
- Clear: State problems explicitly"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "Bash", "task"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Analyze task for pre-planning."""
        self.logger.info(f"Metis analyzing: {task[:100]}...")

        try:
            analysis = self.analyze_task(task)
            return AgentResult(
                success=True,
                content=f"# Pre-Planning Analysis\n\n{analysis}",
                metadata={"type": "pre_planning"}
            )
        except Exception as e:
            self.logger.error(f"Metis error: {e}")
            return AgentResult(success=False, error=str(e))

    def analyze_task(self, task: str) -> str:
        """Analyze task for issues."""
        return f"""## Intent Clarification
[Analysis of what this task likely intends]

## Identified Ambiguities
1. [Potential ambiguity]

## Potential Failure Points
1. [Where this might fail]

## Recommendations
- [What to clarify]"""
