"""Sisyphus - Main orchestrator agent."""

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


@AgentRegistry.register("sisyphus")
class SisyphusAgent(BaseAgent):
    """
    The main orchestrator agent.
    
    Plans, delegates, and executes complex tasks using specialized subagents
    with aggressive parallel execution. Todo-driven workflow.
    
    Named after the Greek myth - perpetually pushing tasks to completion.
    """

    def __init__(self, config: AgentConfig | None = None, **kwargs):
        super().__init__(
            config=config or AgentConfig(
                name="sisyphus",
                model="claude-opus-4-6",
                temperature=0.7,
            ),
            **kwargs
        )
        self.active_tasks: list[dict[str, Any]] = []
        self.delegated_tasks: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "sisyphus"

    def _get_default_system_prompt(self) -> str:
        return """You are Sisyphus, the main orchestrator.

Your role is to plan, delegate, and drive complex tasks to completion.

## Core Responsibilities

1. **Planning**: Break down complex goals into manageable tasks
2. **Delegation**: Route tasks to the right specialized agents
3. **Coordination**: Manage parallel execution and dependencies
4. **Verification**: Ensure completed work meets quality standards

## Available Agents

- **hephaestus**: Deep autonomous worker for complex implementation
- **prometheus**: Strategic planner for interview-mode planning
- **oracle**: Architecture and review expert
- **explore**: Fast codebase grep and search
- **librarian**: Documentation and multi-repo analysis
- **atlas**: Todo-list orchestrator for systematic execution

## Workflow

1. Understand the goal thoroughly
2. Create a structured plan with task dependencies
3. Delegate independent tasks to specialized agents
4. Monitor progress and handle failures
5. Verify results and iterate if needed

## Principles

- Aggressive parallelization: Fire independent tasks simultaneously
- Todo-driven: Track all tasks explicitly
- Don't stop until 100% complete
- Prioritize quality and correctness

## Delegation Format

When delegating, include:
- TASK: What needs to be done
- EXPECTED OUTCOME: What constitutes success
- REQUIRED TOOLS: What tools must be used
- MUST DO / MUST NOT DO: Constraints
- CONTEXT: Relevant files and patterns"""

    def get_capabilities(self) -> set[AgentCapability]:
        return {
            AgentCapability.READ,
            AgentCapability.WRITE,
            AgentCapability.EDIT,
            AgentCapability.DELEGATE,
            AgentCapability.EXECUTE,
        }

    def get_restricted_tools(self) -> list[str]:
        return []

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute a complex task by orchestrating subagents."""
        self.logger.info(f"Sisyphus executing: {task[:100]}...")

        try:
            plan = await self.create_plan(task, context)
            
            for step in plan:
                await self.execute_step(step, context)
                
            return AgentResult(
                success=True,
                content=f"Completed: {task}",
                metadata={"steps": len(plan)}
            )
        except Exception as e:
            self.logger.error(f"Sisyphus error: {e}")
            return AgentResult(success=False, error=str(e))

    async def create_plan(self, goal: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Create a structured plan for the goal."""
        tasks = []
        
        if context and context.get("quick", False):
            tasks.append({"action": "direct", "task": goal})
        else:
            tasks.append({"action": "delegate", "agent": "hephaestus", "task": goal})
            
        return tasks

    async def execute_step(self, step: dict[str, Any], context: dict[str, Any] | None = None) -> None:
        """Execute a single plan step."""
        action = step.get("action")
        
        if action == "direct":
            self.logger.info(f"Direct execution: {step.get('task')}")
        elif action == "delegate":
            agent_name = step.get("agent")
            task = step.get("task")
            self.logger.info(f"Delegating to {agent_name}: {task[:50]}...")
            
            if agent_name in AgentRegistry.list_agents():
                agent = AgentRegistry.get(agent_name)
                await agent.execute(task, context)

    async def plan(self, goal: str, constraints: list[str] | None = None) -> list[str]:
        """Create a plan using strategic planning."""
        plan_steps = []
        
        plan_steps.append(f"Analyze goal: {goal}")
        
        if constraints:
            plan_steps.append(f"Consider constraints: {', '.join(constraints)}")
            
        plan_steps.append("Break into implementation tasks")
        plan_steps.append("Execute with verification")
        plan_steps.append("Review and finalize")
        
        return plan_steps
