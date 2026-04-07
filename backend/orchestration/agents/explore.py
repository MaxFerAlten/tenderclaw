"""Explore - Fast codebase grep agent."""

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


@AgentRegistry.register("explore")
class ExploreAgent(BaseAgent):
    """
    Fast codebase exploration and contextual grep.
    
    Quickly find files, patterns, and understand codebase structure.
    Optimized for speed and efficiency.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="explore",
                model="grok-code-fast-1",
                temperature=0.3,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "explore"

    def _get_default_system_prompt(self) -> str:
        return """You are Explore, the fast codebase grep agent.

Your role is to quickly find files, patterns, and understand code structure.

## Capabilities

1. **File Search**: Find files by name pattern
2. **Content Search**: Grep for patterns in files
3. **Code Mapping**: Understand how code is organized
4. **Pattern Recognition**: Find common patterns and conventions

## Output Format

For searches:
```
# Search Results: [pattern]

## Files Found
| File | Line | Match |
|------|------|-------|
| path/file.ts | 42 | context |

## Summary
- 5 files matched
- 12 total occurrences
```

For exploration:
```
# Exploration: [topic]

## File Structure
[Relevant files and their purpose]

## Key Findings
1. [Finding 1]
2. [Finding 2]

## Related Patterns
[How this is typically implemented]
```

## Principles

- Fast: Return results quickly
- Precise: Include relevant context
- Organized: Structure information clearly
- Actionable: Tell what to do with findings"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "Bash", "task"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Explore the codebase."""
        self.logger.info(f"Explore searching: {task[:100]}...")

        try:
            search_type = context.get("search_type", "content") if context else "content"
            
            if search_type == "file":
                return await self.find_files(task, context)
            elif search_type == "structure":
                return await self.explore_structure(task, context)
            else:
                return await self.search_content(task, context)
        except Exception as e:
            self.logger.error(f"Explore error: {e}")
            return AgentResult(success=False, error=str(e))

    async def find_files(self, pattern: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Find files matching a pattern."""
        return AgentResult(
            success=True,
            content=f"# File Search: {pattern}\n\n## Results\n\n[Files matching pattern]",
            metadata={"pattern": pattern, "count": 0}
        )

    async def search_content(self, pattern: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Search file contents."""
        return AgentResult(
            success=True,
            content=f"# Content Search: {pattern}\n\n## Results\n\n| File | Line | Match |\n|------|------|-------|\n| ... | ... | ... |",
            metadata={"pattern": pattern, "files": 0, "matches": 0}
        )

    async def explore_structure(self, topic: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Explore code structure."""
        return AgentResult(
            success=True,
            content=f"# Structure Exploration: {topic}\n\n## Files\n\n[Relevant files]\n\n## Key Findings\n\n1. [Finding]",
            metadata={"topic": topic}
        )
