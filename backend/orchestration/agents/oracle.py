"""Oracle - Architecture and review agent."""

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


@AgentRegistry.register("oracle")
class OracleAgent(BaseAgent):
    """
    Architecture decisions, code review, debugging.
    
    Read-only consultation with stellar logical reasoning and deep analysis.
    Provides architecture guidance, reviews code, and helps debug issues.
    
    Named after the mythical oracles who provided wisdom and foresight.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="oracle",
                model="gpt-5.4",
                temperature=0.5,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "oracle"

    def _get_default_system_prompt(self) -> str:
        return """You are Oracle, the architecture and review expert.

Your role is to provide deep analysis, architectural guidance, and code review.

## Expertise Areas

1. **Architecture**: System design, patterns, scalability
2. **Code Review**: Quality, maintainability, best practices
3. **Debugging**: Root cause analysis, problem solving
4. **Performance**: Optimization, efficiency, bottlenecks

## Consultation Format

When asked to review or analyze:

### For Architecture
```
## Analysis

### Current Understanding
[What the system does]

### Strengths
- [What's working well]

### Weaknesses
- [What's problematic]

### Recommendations
1. [Specific recommendation]
2. ...

### Risks
- [Potential issues with recommendations]
```

### For Code Review
```
## Review: [file/feature]

### Summary
[Overall assessment]

### Issues
| Severity | Location | Issue | Suggestion |
|----------|----------|-------|------------|
| High | line 42 | Bug | Fix this |

### Suggestions
- [Improvements]

### Approval: APPROVED / CHANGES REQUESTED
```

### For Debugging
```
## Debug: [problem]

### Symptom
[What's happening]

### Possible Causes
1. [Cause 1]
2. [Cause 2]

### Investigation Steps
1. [Check this first]
2. ...

### Solution
[If found]
```

## Principles

- Evidence-based: Ground recommendations in facts
- Balanced: Consider tradeoffs, not just best practices
- Actionable: Provide specific, implementable guidance
- Conservative: Prefer proven patterns for critical systems"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "Bash", "task"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Provide analysis or review."""
        self.logger.info(f"Oracle consulting: {task[:100]}...")

        try:
            review_type = context.get("type", "general") if context else "general"
            
            if review_type == "architecture":
                return await self.architecture_review(task, context)
            elif review_type == "code":
                return await self.code_review(task, context)
            elif review_type == "debug":
                return await self.debug_analysis(task, context)
            else:
                return await self.general_consultation(task, context)
        except Exception as e:
            self.logger.error(f"Oracle error: {e}")
            return AgentResult(success=False, error=str(e))

    async def architecture_review(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Provide architecture guidance."""
        return AgentResult(
            success=True,
            content=f"# Architecture Review\n\n## Analysis\n\n{task}\n\n## Recommendations\n\n[Oracle guidance]",
            metadata={"type": "architecture"}
        )

    async def code_review(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Review code."""
        return AgentResult(
            success=True,
            content=f"# Code Review\n\n## Summary\n\n{task}\n\n## Issues\n\n[Issues identified]\n\n## Approval: CHANGES REQUESTED",
            metadata={"type": "code_review"}
        )

    async def debug_analysis(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Analyze debugging problem."""
        return AgentResult(
            success=True,
            content=f"# Debug Analysis\n\n## Symptom\n\n{task}\n\n## Possible Causes\n\n1. [Cause 1]\n2. [Cause 2]\n\n## Investigation Steps\n\n1. [Step 1]\n\n## Solution\n\n[If found]",
            metadata={"type": "debug"}
        )

    async def general_consultation(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """General consultation."""
        return AgentResult(
            success=True,
            content=f"# Consultation\n\n## Question\n\n{task}\n\n## Analysis\n\n[Oracle analysis]",
            metadata={"type": "general"}
        )

    async def review(self, content: str) -> AgentResult:
        """Review content and provide feedback."""
        return await self.code_review(content, {"type": "code"})
