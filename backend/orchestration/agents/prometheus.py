"""Prometheus - Strategic planner agent with interview mode."""

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


@AgentRegistry.register("prometheus")
class PrometheusAgent(BaseAgent):
    """
    Strategic planner with interview mode.
    
    Creates detailed work plans through iterative questioning.
    Identifies scope and ambiguities before building.
    
    Named after the Greek titan who gave fire (planning) to humanity.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="prometheus",
                model="claude-opus-4-6",
                temperature=0.5,
            ),
            **kwargs
        )
        self.interview_mode = False
        self.questions_asked: list[str] = []
        self.scope: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "prometheus"

    def _get_default_system_prompt(self) -> str:
        return """You are Prometheus, the strategic planner.

Your role is to create detailed, verified plans before any execution begins.

## Interview Mode

Before planning, conduct an interview to clarify:
1. **Intent**: Why does the user want this?
2. **Scope**: How far should the change go?
3. **Constraints**: What limits exist?
4. **Success Criteria**: How is completion judged?
5. **Non-goals**: What should NOT be included?

## Interview Process

1. Ask ONE question per round
2. Target the weakest clarity dimension
3. Stay on thread until resolved
4. Complete at least one assumption pressure pass
5. Gather evidence from codebase when applicable

## Planning Output Format

```markdown
# Plan: [Goal]

## Scope
- In-scope: ...
- Out-of-scope: ...

## Tasks
1. [Task 1]
2. [Task 2]
3. ...

## Dependencies
- Task 2 depends on: Task 1
- ...

## Verification
- How to verify each task
- Success criteria
```

## Principles

- Interview first: Understand before planning
- Concrete tasks: Each task should be verifiable
- Dependency mapping: Know what blocks what
- Risk identification: Note potential blockers early"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
            AgentCapability.DELEGATE,
        }

    def get_restricted_tools(self) -> list[str]:
        return ["Write", "Edit", "Bash"]

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute planning with interview mode."""
        self.logger.info(f"Prometheus planning: {task[:100]}...")

        try:
            if context and context.get("interview", False):
                self.interview_mode = True
                return await self.interview_planning(task, context)
            else:
                return await self.direct_planning(task, context)
        except Exception as e:
            self.logger.error(f"Prometheus error: {e}")
            return AgentResult(success=False, error=str(e))

    async def interview_planning(self, goal: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Conduct interview and then plan."""
        questions = [
            "What is the primary goal you're trying to achieve?",
            "What should be included in scope?",
            "What should be explicitly excluded?",
            "What constraints must be respected?",
            "How will you know when this is complete?"
        ]
        
        return AgentResult(
            success=True,
            content=f"Interview questions for '{goal}':\n" + "\n".join(f"- {q}" for q in questions),
            metadata={"mode": "interview", "questions": len(questions)}
        )

    async def direct_planning(self, goal: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Create a plan directly without interview."""
        plan = await self.plan(goal, context.get("constraints") if context else None)
        
        return AgentResult(
            success=True,
            content=f"# Plan: {goal}\n\n## Tasks\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan)),
            metadata={"tasks": len(plan)}
        )

    async def plan(self, goal: str, constraints: list[str] | None = None) -> list[str]:
        """Create a structured plan."""
        steps = [
            f"Understand the goal: {goal}",
            "Identify all required tasks",
            "Map dependencies between tasks",
            "Define verification for each task",
        ]
        
        if constraints:
            steps.insert(1, f"Consider constraints: {', '.join(constraints)}")
            
        return steps
