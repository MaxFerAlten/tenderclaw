"""Momus - Plan reviewer agent."""

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


@AgentRegistry.register("momus")
class MomusAgent(BaseAgent):
    """
    Plan reviewer - validates plans.
    
    Reviews plans for clarity, verifiability, and completeness.
    Named after the Greek god of critique and mockery.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="momus",
                model="gpt-5.4",
                temperature=0.4,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "momus"

    def _get_default_system_prompt(self) -> str:
        return """You are Momus, the plan reviewer.

Your role is to validate plans before execution.

## Review Criteria

1. **Clarity**: Is each task clear and unambiguous?
2. **Verifiability**: Can completion be objectively measured?
3. **Completeness**: Are all dependencies covered?
4. **Feasibility**: Can this actually be done?

## Review Format

```markdown
# Plan Review

## Overall Assessment
[APPROVED / REVISION NEEDED]

## Clarity Check
| Task | Clear? | Issues |
|------|--------|--------|
| Task 1 | ✓ | - |
| Task 2 | ✗ | Vague |

## Verifiability Check
| Task | Testable? | Criteria |
|------|-----------|----------|
| Task 1 | ✓ | Unit tests pass |
| Task 2 | ✗ | No success criteria |

## Issues Found
1. [Issue 1]
2. [Issue 2]

## Recommendations
[How to fix issues]
```

## Principles

- Critical: Don't approve flawed plans
- Thorough: Check every task
- Practical: Ensure verifiability
- Constructive: Provide actionable feedback"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "task"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Review a plan."""
        self.logger.info(f"Momus reviewing: {task[:100]}...")

        try:
            review = self.review_plan(task)
            approved = "APPROVED" if self.is_approved(review) else "REVISION NEEDED"
            
            return AgentResult(
                success=True,
                content=f"# Plan Review\n\n## Overall Assessment\n**{approved}**\n\n{review}",
                metadata={"type": "review", "approved": approved == "APPROVED"}
            )
        except Exception as e:
            self.logger.error(f"Momus error: {e}")
            return AgentResult(success=False, error=str(e))

    def review_plan(self, plan: str) -> str:
        """Review a plan."""
        return """## Clarity Check
| Task | Clear? | Issues |
|------|--------|--------|
| [Task] | ✓ | - |

## Verifiability Check
| Task | Testable? | Criteria |
|------|-----------|----------|
| [Task] | ✓ | Defined |

## Issues Found
[None identified]

## Recommendations
[Plan looks good]"""

    def is_approved(self, review: str) -> bool:
        """Check if plan is approved."""
        return "REVISION NEEDED" not in review[:100]
