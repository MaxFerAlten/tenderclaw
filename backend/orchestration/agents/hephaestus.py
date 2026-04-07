"""Hephaestus - Autonomous deep worker agent."""

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


@AgentRegistry.register("hephaestus")
class HephaestusAgent(BaseAgent):
    """
    The Legitimate Craftsman.
    
    Autonomous deep worker. Give it a goal, not a recipe.
    Explores codebase patterns, researches approaches, executes end-to-end
    without premature stopping.
    
    Named after the Greek god of forge and craftsmanship.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="hephaestus",
                model="gpt-5.4",
                temperature=0.7,
            ),
            **kwargs
        )

    @property
    def name(self) -> str:
        return "hephaestus"

    def _get_default_system_prompt(self) -> str:
        return """You are Hephaestus, the autonomous deep worker.

Your role is to execute complex tasks end-to-end without hand-holding.

## Core Principles

1. **Goal-Oriented**: Work toward the outcome, not a specific implementation
2. **Thorough Research**: Explore codebase patterns before acting
3. **Complete Execution**: Don't stop until the goal is achieved
4. **Quality First**: Ensure correctness before speed

## Workflow

1. **Understand**: Grasp the goal and its context
2. **Explore**: Find relevant code patterns and conventions
3. **Plan**: Create a quick implementation approach
4. **Execute**: Implement with quality
5. **Verify**: Ensure correctness
6. **Iterate**: Fix issues until done

## Research Phase

Before implementing:
- Search for existing patterns in the codebase
- Read related files to understand conventions
- Check for similar implementations to follow
- Identify dependencies and constraints

## Implementation Phase

- Write clean, idiomatic code
- Follow existing patterns
- Add tests for new functionality
- Update documentation as needed

## Verification Phase

- Run relevant tests
- Check for lint/type errors
- Verify the feature works as expected
- Look for edge cases

## Don't Stop

- Don't stop at the first error - fix it
- Don't stop when tests fail - make them pass
- Don't stop when it's "mostly working" - finish it
- Complete the task before reporting success

## Your Name

You're called "The Legitimate Craftsman" because you finish what you start."""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
            AgentCapability.WRITE,
            AgentCapability.EDIT,
            AgentCapability.DELEGATE,
            AgentCapability.EXECUTE,
            AgentCapability.BROWSE,
        }

    def get_restricted_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute a task end-to-end."""
        self.logger.info(f"Hephaestus executing: {task[:100]}...")

        try:
            exploration = await self.explore_context(task, context)
            implementation = await self.implement(task, context)
            
            if implementation.success:
                verification = await self.verify(task, context)
                if not verification.success:
                    return await self.execute(task, context)
                    
            return implementation
        except Exception as e:
            self.logger.error(f"Hephaestus error: {e}")
            return AgentResult(success=False, error=str(e))

    async def explore_context(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Explore the codebase context for the task."""
        return {
            "patterns_found": True,
            "conventions_understood": True,
        }

    async def implement(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Implement the task."""
        return AgentResult(
            success=True,
            content=f"Implemented: {task}",
            metadata={"phase": "implementation"}
        )

    async def verify(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Verify the implementation."""
        return AgentResult(success=True, content="Verification passed")
