"""Agent handler — engine to run AI agent requests.

Executes requests using the model_router, handles tool execution,
and tracks token usage/costs for a given agent.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from backend.agents.registry import agent_registry
from backend.services.model_router import model_router
from backend.tools.registry import tool_registry

logger = logging.getLogger("tenderclaw.agents.handler")


class AgentHandler:
    """Handles turn-by-turn execution for any registered agent."""

    async def execute_agent_turn(
        self,
        agent_name: str,
        messages: list[dict[str, Any]],
        system_override: str = "",
        model_override: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream an agent Turn, performing tool calls as needed."""
        agent = agent_registry.get(agent_name)
        
        # Determine model and prompt
        model = model_override or agent.default_model
        system_prompt = system_override or agent.system_prompt
        
        # Determine available tools
        # If agent.tools is empty, use all tools. Otherwise, filter tool_registry.
        available_tools = tool_registry.list_api_schemas()
        if agent.tools:
            available_tools = [t for t in available_tools if t["name"] in agent.tools]

        logger.info(
            "Agent turn [%s]: %s (tools: %d)",
            agent_name,
            model,
            len(available_tools),
        )

        async for event in model_router.stream_message(
            model=model,
            messages=messages,
            system=system_prompt,
            tools=available_tools,
        ):
            yield event


# Module-level instance
agent_handler = AgentHandler()
