"""Superpowers Plugin — integrates the external superpowers library.

This plugin bridges TenderClaw with Jesse Vincent's 'superpowers' 
multi-agent workflow and skills.
"""

from __future__ import annotations

import os
from typing import Any

from backend.plugins.base import BasePlugin
from backend.tools.registry import ToolRegistry
from backend.agents.registry import AgentRegistry

SUPERPOWERS_PATH = r"d:\MY_AI\claude-code\superpowers"


class SuperpowersPlugin(BasePlugin):
    """Integrates Jesse's Superpowers skill library and workflow-driven development."""

    @property
    def name(self) -> str:
        return "superpowers"

    @property
    def version(self) -> str:
        return "2.1.0"

    def on_init(self, config: dict[str, Any]) -> None:
        """Verify the path exists and log metadata."""
        if not os.path.exists(SUPERPOWERS_PATH):
            raise FileNotFoundError(f"Superpowers not found at {SUPERPOWERS_PATH}")

    def on_register_skills(self, skills_path: str) -> None:
        """Register the skills directory from superpowers."""
        # This will be handled by the session's prompt builder
        # But we can store it here for the plugin loader
        pass

    def on_register_agents(self, registry: AgentRegistry) -> None:
        """Register specialized agents from superpowers."""
        # For example, Jesse's SDD (Subagent-Driven-Development)
        # can be wrapped in a TenderClaw AgentDefinition
        pass

    def on_register_tools(self, registry: ToolRegistry) -> None:
        """Register unique superpower tools (if any)."""
        pass
