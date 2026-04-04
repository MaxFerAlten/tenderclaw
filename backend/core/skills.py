"""Skills Loader — manage and inject superpower skills.

Skills are directories containing SKILL.md files.
This module searches designated paths for skills to show the agent.
"""

from __future__ import annotations

import os
from pathlib import Path

SKILLS_PATHS = [
    Path(__file__).parent.parent.parent / "skills",
    Path(r"d:\MY_AI\claude-code\superpowers\skills"),
]


def list_available_skills() -> list[dict[str, str]]:
    """Return a list of all skills found in the SKILLS_PATHS."""
    skills = []
    for base_path in SKILLS_PATHS:
        if not base_path.exists():
            continue
        for skill_dir in base_path.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skills.append({
                    "name": skill_dir.name,
                    "path": str(skill_dir / "SKILL.md"),
                    "description": _extract_description(skill_dir / "SKILL.md")
                })
    return skills


def build_skills_instruction() -> str:
    """Consolidate all skills into a prompt section for the agent."""
    skills = list_available_skills()
    if not skills:
        return ""

    instruction = "\n## Superpowers Skills\n"
    instruction += "You have access to specialized 'skills' for complex tasks.\n"
    instruction += "If a task matches one of these, you MUST read the SKILL.md file before proceeding:\n"
    
    for s in skills:
        instruction += f"- **{s['name']}**: {s['description']}\n"
    
    instruction += "\nTo read a skill, use `Read` on its path listed above."
    return instruction


def _extract_description(skill_path: Path) -> str:
    """Very simple description extraction from markdown frontmatter or top lines."""
    try:
        content = skill_path.read_text("utf-8")
        if "description:" in content:
            # Simple line-based extract
            for line in content.split("\n"):
                if "description:" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "Specialized workflow skill."
