"""Atlas - Todo-list orchestrator agent."""

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


@AgentRegistry.register("atlas")
class AtlasAgent(BaseAgent):
    """
    Todo-list orchestrator.
    
    Executes planned tasks systematically, managing todo items
    and coordinating work. Named after Atlas who holds up the sky.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="atlas",
                model="claude-sonnet-4-6",
                temperature=0.5,
            ),
            **kwargs
        )
        self.tasks: list[dict[str, Any]] = []
        self.current_task: int = 0

    @property
    def name(self) -> str:
        return "atlas"

    def _get_default_system_prompt(self) -> str:
        return """You are Atlas, the todo orchestrator.

Your role is to systematically execute planned tasks.

## Task Management

1. **Create**: Break plan into actionable tasks
2. **Track**: Monitor progress through task list
3. **Execute**: Work through tasks systematically
4. **Coordinate**: Handle dependencies between tasks

## Todo Format

```markdown
## Todo: [Goal]

- [ ] Task 1
- [ ] Task 2 (blocked by: Task 1)
- [ ] Task 3

### Progress
- Completed: 0/3
- Current: Task 1
```

## Workflow

1. Receive a plan
2. Break into atomic tasks
3. Identify dependencies
4. Execute tasks in dependency order
5. Update todo status as you progress
6. Report completion when done

## Principles

- Systematic: Follow the plan exactly
- Thorough: Complete all tasks
- Organized: Track progress clearly
- Coordinate: Don't start blocked tasks"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
            AgentCapability.WRITE,
            AgentCapability.EDIT,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["task", "call_omo_agent"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute tasks from a plan."""
        self.logger.info(f"Atlas orchestrating: {task[:100]}...")

        try:
            plan = context.get("plan", []) if context else []
            
            self.tasks = plan
            completed = 0
            
            for i, item in enumerate(self.tasks):
                self.current_task = i
                await self.execute_task(item)
                completed += 1
                
            return AgentResult(
                success=True,
                content=f"Completed {completed}/{len(self.tasks)} tasks",
                metadata={"completed": completed, "total": len(self.tasks)}
            )
        except Exception as e:
            self.logger.error(f"Atlas error: {e}")
            return AgentResult(success=False, error=str(e))

    async def execute_task(self, task: dict[str, Any]) -> None:
        """Execute a single task."""
        self.logger.info(f"Atlas executing task: {task}")
