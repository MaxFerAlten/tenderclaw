"""Librarian - Documentation and multi-repo analysis agent."""

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


@AgentRegistry.register("librarian")
class LibrarianAgent(BaseAgent):
    """
    Multi-repo analysis, documentation lookup, OSS implementation examples.
    
    Deep codebase understanding with evidence-based answers.
    Great for finding how things are implemented elsewhere.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="librarian",
                model="minimax-m2.7",
                temperature=0.4,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "librarian"

    def _get_default_system_prompt(self) -> str:
        return """You are Librarian, the documentation and research expert.

Your role is to find, analyze, and explain code and documentation.

## Capabilities

1. **Documentation Lookup**: Find relevant docs
2. **Implementation Research**: How is something implemented?
3. **Multi-repo Analysis**: Compare implementations across repos
4. **Pattern Discovery**: Find common approaches

## Output Format

For documentation:
```
# Documentation: [topic]

## Relevant Docs
- [Doc 1]: [URL/Path]
- [Doc 2]: [URL/Path]

## Key Points
1. [Point 1]
2. [Point 2]
```

For implementation research:
```
# Implementation Research: [feature]

## Found In
- [Repo 1]: [path]
- [Repo 2]: [path]

## Approach Analysis
[How each repo implements this]

## Best Practice
[Recommended approach]
```

## Principles

- Evidence-based: Quote actual code and docs
- Thorough: Check multiple sources
- Organized: Structure findings clearly
- Educational: Explain the "why" not just the "what\""""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
            AgentCapability.BROWSE,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "Bash", "task"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Research and analyze."""
        self.logger.info(f"Librarian researching: {task[:100]}...")

        try:
            return AgentResult(
                success=True,
                content=f"# Research: {task}\n\n## Findings\n\n[Evidence-based analysis]",
                metadata={"type": "research"}
            )
        except Exception as e:
            self.logger.error(f"Librarian error: {e}")
            return AgentResult(success=False, error=str(e))
