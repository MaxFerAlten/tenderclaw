"""System prompt builder — assembles the system prompt for each session.

Mirrors Claude Code's modular prompt architecture with cacheable + dynamic sections.
"""

from __future__ import annotations

import logging
import os
import platform
from datetime import UTC, datetime

logger = logging.getLogger("tenderclaw.core.system_prompt")


def _platform_context() -> str:
    """Build an OS/shell section so the model picks the right commands.

    Without this the model silently assumes POSIX and emits `ls -la`, `cat`,
    `grep` etc. on Windows where `cmd.exe` rejects them, producing a loop of
    failed tool calls (and repeated permission prompts) that looks like a
    hang to the user.
    """
    sysname = platform.system()  # 'Windows', 'Linux', 'Darwin'
    release = platform.release()
    arch = platform.machine()

    if sysname == "Windows":
        shell = "cmd.exe (Windows command prompt — POSIX utilities like ls/cat/grep are NOT available)"
        guidance = (
            "- File listing: use `dir` (cmd) or `Get-ChildItem` (powershell), NOT `ls`.\n"
            "- Read file: use `type file.txt` (cmd) or `Get-Content file.txt` (powershell), NOT `cat`.\n"
            "- Search: use `findstr` (cmd) or `Select-String` (powershell), NOT `grep`.\n"
            "- For multi-step POSIX-style scripting, prefix the whole command with `powershell -Command \"...\"`.\n"
            "- Path separators: backslash `\\` works in cmd; in powershell both `/` and `\\` work.\n"
            "- PREFER the specialised tools (Grep, Glob, FileRead, FileWrite) over Bash for portable file ops."
        )
    elif sysname == "Darwin":
        shell = os.environ.get("SHELL", "/bin/zsh")
        guidance = "- Standard POSIX tools available: ls, cat, grep, find, sed, awk, etc."
    else:  # Linux / other Unix
        shell = os.environ.get("SHELL", "/bin/bash")
        guidance = "- Standard POSIX tools available: ls, cat, grep, find, sed, awk, etc."

    return (
        "\n## Platform\n"
        f"- OS: {sysname} {release} ({arch})\n"
        f"- Shell: {shell}\n"
        "### Shell guidance\n"
        f"{guidance}"
    )

BASE_SYSTEM_PROMPT = """\
You are TenderClaw, an advanced AI coding assistant powered by multiple AI models.
You help users with software development tasks by reading, writing, and editing code,
running shell commands, searching codebases, and managing projects.

## Core Principles
- Be direct and concise. Avoid filler phrases and unnecessary commentary.
- Write production-quality code that reads like a senior engineer wrote it.
- Always verify your changes work before reporting success.
- When uncertain, ask the user rather than guessing.
- Reply in the same language as the user's latest message unless they ask otherwise.
- Do not reveal private reasoning, scratchpad notes, or internal analysis. Provide the final answer only.
- Never emit hidden-reasoning tags such as <antThinking>, <thinking>, <think>, <analysis>, or <scratchpad>.

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
    wisdom_context: str = "",
    memory_context: str = "",
) -> str:
    """Build the full system prompt for a session.

    Composes: base prompt + skills + contextual wisdom + memory context + dynamic context + user append.

    Args:
        working_directory: The active working directory shown to the model.
        append: Optional extra instructions appended at the end.
        wisdom_context: Pre-built wisdom block from memory_manager (replaces the
            old static wisdom lookup done here — avoids duplicate retrieval).
        memory_context: Pre-built MEMORY.md context from memdir.
    """
    parts = [BASE_SYSTEM_PROMPT]

    # Superpowers Skill Injection
    skills = build_skills_instruction()
    if skills:
        parts.append(skills)

    # Contextual wisdom — injected by conversation.py via memory_manager
    if wisdom_context:
        parts.append(f"\n{wisdom_context}")
    else:
        # Fallback: static wisdom lookup when memory_manager is unavailable
        try:
            from backend.memory.wisdom import wisdom_store
            relevant = wisdom_store.find_relevant(working_directory.split("/")[-1])
            if relevant:
                wisdom_text = "\n".join(
                    f"- [{w.task_type}] {w.description}: {w.solution_pattern}"
                    for w in relevant[:3]
                )
                parts.append(f"\n## Accumulated Wisdom\n{wisdom_text}")
        except Exception as exc:
            logger.debug("Wisdom injection skipped: %s", exc)

    # MEMORY.md context — injected by conversation.py via memdir
    if memory_context:
        parts.append(f"\n{memory_context}")

    # Dynamic section — not cacheable
    parts.append(f"\n## Context\n- Current date: {datetime.now(UTC).strftime('%Y-%m-%d')}")
    parts.append(f"- Working directory: {working_directory}")

    # Platform / shell guidance — critical so the model doesn't emit POSIX
    # commands on Windows (ls, cat, grep) which cmd.exe rejects, producing a
    # retry loop that looks like a hang to the user.
    parts.append(_platform_context())

    if append:
        parts.append(f"\n## Additional Instructions\n{append}")

    return "\n".join(parts)
