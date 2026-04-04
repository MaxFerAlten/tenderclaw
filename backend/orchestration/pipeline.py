"""Team Pipeline — orchestrate specialized agents in sequence for a task.

Implements the plan -> exec -> verify loop.
Each stage uses a different agent role.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Callable, Awaitable

from backend.agents.handler import agent_handler
from backend.orchestration.intent_gate import Intent
from backend.schemas.ws import WSAgentSwitch

logger = logging.getLogger("tenderclaw.orchestration.pipeline")

# WebSocket sender type
SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class TeamPipeline:
    """Orchestrate multiple agents to complete a complex task."""

    async def run_implement_pipeline(
        self,
        task: str,
        messages: list[dict[str, Any]],
        send: SendFn,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the Standard Implementation Pipeline:
        1. **Metis** (Strategy/Plan)
        2. **Sisyphus** (Execution)
        3. **Momus** (Verification/Critique)
        """
        
        # Stage 1: Planning with Metis
        logger.info("Pipeline Stage 1: Planning (Metis)")
        await send(WSAgentSwitch(agent_name="metis", task="planning").model_dump())
        
        plan_messages = messages + [{"role": "user", "content": f"Create a detailed implementation plan for: {task}"}]
        plan_results = []
        async for part in agent_handler.execute_agent_turn("metis", plan_results + plan_messages):
            if part.get("type") == "assistant_text":
                plan_results.append(part["delta"])
                yield part
        
        full_plan = "".join(plan_results)
        
        # Stage 2: Execution with Sisyphus
        logger.info("Pipeline Stage 2: Execution (Sisyphus)")
        await send(WSAgentSwitch(agent_name="sisyphus", task="executing plan").model_dump())
        
        exec_messages = messages + [
            {"role": "assistant", "content": f"Here is the plan:\n{full_plan}"},
            {"role": "user", "content": "Execute the plan now. Use tools as needed."}
        ]
        
        async for part in agent_handler.execute_agent_turn("sisyphus", exec_messages):
             yield part # Sisyphus will use tools to perform changes

        # Stage 3: Verification with Momus
        logger.info("Pipeline Stage 3: Verification (Momus)")
        await send(WSAgentSwitch(agent_name="momus", task="auditing results").model_dump())
        
        # In this simplistic version, we'll just ask Momus to audit.
        # Real Phase 4 would run tests automatically.
        audit_messages = messages + [{"role": "user", "content": "Audit the implementation. Is it correct and safe?"}]
        async for part in agent_handler.execute_agent_turn("momus", audit_messages):
            yield part

        # Final back to Sisyphus for confirmation
        await send(WSAgentSwitch(agent_name="sisyphus").model_dump())


# Module-level instance
team_pipeline = TeamPipeline()
