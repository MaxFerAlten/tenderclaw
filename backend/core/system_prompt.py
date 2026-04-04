"""System prompt builder — assembles the system prompt for each session.

Mirrors Claude Code's modular prompt architecture with cacheable + dynamic sections.
"""

from __future__ import annotations

from datetime import datetime


BASE_SYSTEM_PROMPT = """\
You are TenderClaw, an advanced AI coding assistant powered by multiple AI models.
You help users with software development tasks by reading, writing, and editing code,
running shell commands, searching codebases, and managing projects.

## Core Principles
- Be direct and concise. Avoid filler phrases and unnecessary commentary.
- Write production-quality code that reads like a senior engineer wrote it.
- Always verify your changes work before reporting success.
- When uncertain, ask the user rather than guessing.

## Tools
You have access to tools for file operations, shell commands, and code search.
Use them proactively to explore the codebase and verify your work.

## Important Rules
- NEVER output secrets, API keys, or credentials.
- ALWAYS explain what you're doing before making changes.
- Prefer editing existing files over creating new ones.
- Keep files under 200 lines when possible.
"""


from backend.core.skills import build_skills_instruction


def build_system_prompt(
    working_directory: str = ".",
    append: str = "",
) -> str:
    """Build the full system prompt for a session.

    Composes: base prompt + dynamic context + superpowers skills + user append.
    """
    parts = [BASE_SYSTEM_PROMPT]

    # Superpowers Skill Injection
    skills = build_skills_instruction()
    if skills:
        parts.append(skills)

    # Wisdom injection — relevant past learnings
    try:
        from backend.memory.wisdom import wisdom_store
        relevant = wisdom_store.find_relevant(working_directory.split("/")[-1])
        if relevant:
            wisdom_text = "\n".join(
                f"- [{w.task_type}] {w.description}: {w.solution_pattern}"
                for w in relevant[:5]
            )
            parts.append(f"\n## Accumulated Wisdom\n{wisdom_text}")
    except Exception:
        pass

    # Dynamic section — not cacheable
    parts.append(f"\n## Context\n- Current date: {datetime.utcnow().strftime('%Y-%m-%d')}")
    parts.append(f"- Working directory: {working_directory}")

    if append:
        parts.append(f"\n## Additional Instructions\n{append}")

    return "\n".join(parts)
