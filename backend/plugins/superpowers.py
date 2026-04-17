"""Superpowers Plugin — integrates the external superpowers library.

This plugin bridges TenderClaw with Jesse Vincent's 'superpowers'
multi-agent workflow and skills.

On startup it:
1. Loads agent definitions from superpowers/agents/*.md
2. Registers them in the AgentRegistry as SPECIALIST subagents
3. Loads command definitions from superpowers/commands/*.md
4. Registers each as a SuperpowerCommandTool in the ToolRegistry
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from backend.plugins.base import BasePlugin
from backend.tools.registry import ToolRegistry
from backend.agents.registry import AgentRegistry

logger = logging.getLogger("tenderclaw.plugins.superpowers")

def _resolve_superpowers_path() -> Path:
    """Resolve superpowers path from config, env, or default."""
    from backend.config import settings
    if settings.superpowers_path:
        return Path(settings.superpowers_path)
    env = os.environ.get("SUPERPOWERS_PATH", "")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent / "superpowers"


SUPERPOWERS_PATH = _resolve_superpowers_path()


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
        if not SUPERPOWERS_PATH.exists():
            raise FileNotFoundError(f"Superpowers not found at {SUPERPOWERS_PATH}")
        logger.info("Superpowers plugin init — path: %s", SUPERPOWERS_PATH)

    def on_register_skills(self, skills_path: str) -> None:
        """Register the skills directory from superpowers and system skills."""
        # Register superpowers external skills path
        try:
            from backend.core import skills as skills_module
            sp_skills = SUPERPOWERS_PATH / "skills"
            if sp_skills.exists():
                skills_module.add_skills_path(str(sp_skills))
                logger.info("Registered superpowers skills path: %s", sp_skills)
        except Exception as exc:
            logger.warning("Could not register superpowers skills: %s", exc)

        # Register system skills (brainstorming, writing-plans) with priority loading
        try:
            from backend.plugins.superpowers_loader import load_skills_from_markdown
            from backend.core import skills as skills_module

            local_skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
            descriptors = load_skills_from_markdown(local_skills_dir)

            system_skills = [d for d in descriptors if d.get("system")]
            for desc in system_skills:
                logger.info(
                    "System skill loaded: %s (trigger=%s)",
                    desc["name"], desc["trigger"],
                )
            self._system_skills = system_skills
            logger.info("Loaded %d system skills", len(system_skills))
        except Exception as exc:
            logger.warning("Could not load system skills: %s", exc)
            self._system_skills = []

    def get_system_skills(self) -> list[dict]:
        """Return loaded system skills."""
        return getattr(self, "_system_skills", [])

    def should_activate_design_gate(self, user_message: str) -> dict | None:
        """Check if user message should activate a system design skill.

        Returns the matching system skill descriptor, or None.
        """
        text_lower = user_message.lower()
        design_triggers = [
            "brainstorm", "design", "spec", "architecture",
            "let's think", "think first", "design first", "before coding",
        ]
        plan_triggers = [
            "writing-plan", "writing plan", "implementation plan",
            "break it down", "task list", "decompose",
        ]

        for skill in self.get_system_skills():
            trigger = skill.get("trigger", "")
            if trigger in text_lower:
                return skill

        # Fuzzy matching on design intent keywords
        for keyword in design_triggers:
            if keyword in text_lower:
                for skill in self.get_system_skills():
                    if skill["name"] == "brainstorming":
                        return skill

        for keyword in plan_triggers:
            if keyword in text_lower:
                for skill in self.get_system_skills():
                    if skill["name"] == "writing-plans":
                        return skill

        return None

    def on_register_agents(self, registry: AgentRegistry) -> None:
        """Load and register agents from superpowers/agents/*.md."""
        from backend.plugins.superpowers_loader import load_agents_from_markdown
        from backend.schemas.agents import AgentCategory, AgentCost, AgentDefinition, AgentMode

        agents_dir = SUPERPOWERS_PATH / "agents"
        descriptors = load_agents_from_markdown(agents_dir)

        for desc in descriptors:
            # Prefix name to avoid collision with built-ins
            agent_name = f"sp_{desc['name']}"
            agent = AgentDefinition(
                name=agent_name,
                description=f"[Superpowers] {desc['description']}",
                mode=AgentMode.SUBAGENT,
                category=AgentCategory.SPECIALIST,
                cost=AgentCost.CHEAP,
                default_model=desc.get("model", "claude-sonnet-4-20250514"),
                system_prompt=desc["system_prompt"],
                tools=[],
            )
            registry.register(agent)
            logger.info("Registered superpowers agent: %s", agent_name)

        if descriptors:
            logger.info("Registered %d superpowers agents", len(descriptors))

    def on_register_tools(self, registry: ToolRegistry) -> None:
        """Load and register commands from superpowers/commands/*.md."""
        from backend.plugins.superpowers_loader import load_commands_from_markdown
        from backend.tools.superpowers_tool import SuperpowerCommandTool

        commands_dir = SUPERPOWERS_PATH / "commands"
        descriptors = load_commands_from_markdown(commands_dir)

        for desc in descriptors:
            tool = SuperpowerCommandTool(
                name=desc["name"],
                description=desc["description"],
                body=desc["body"],
            )
            registry.register(tool)
            logger.info("Registered superpowers tool: %s", desc["name"])

        if descriptors:
            logger.info("Registered %d superpowers command tools", len(descriptors))
