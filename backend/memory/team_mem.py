"""Team Memory — team memory paths and prompts for collaborative contexts.

Team memory is strictly scoped to MemoryScope.TEAM. It must never contain
user-personal preferences (those go to MemoryScope.USER) or ephemeral session
data (MemoryScope.SESSION).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.memory.memory_types import MemoryEntry, MemoryMetadata, MemoryScope, MemoryType
from backend.memory.keyword_extractor import extract_keywords

logger = logging.getLogger("tenderclaw.memory.team")

TEAM_MEMORY_DIRS = [
    ".team/memory",
    ".tenderclaw/team",
    "team/memory",
    ".memory/team",
]

TEAM_MEMORY_FILES = [
    "MEMORY.md",
    "team-memory.md",
    ".team-memory.md",
    "shared-memory.md",
]

TEAM_MEMORY_SECTIONS = [
    "## Team Context",
    "## Team Memory",
    "## Shared Knowledge",
    "## Team Preferences",
    "## Onboarding",
]


def get_team_memory_paths(project_root: str | Path = ".") -> list[Path]:
    """Get all possible team memory file paths."""
    root = Path(project_root)
    paths: list[Path] = []

    for dirname in TEAM_MEMORY_DIRS:
        dir_path = root / dirname
        if dir_path.exists() and dir_path.is_dir():
            for filename in TEAM_MEMORY_FILES:
                file_path = dir_path / filename
                if file_path.exists():
                    paths.append(file_path)

    for filename in TEAM_MEMORY_FILES:
        file_path = root / filename
        if file_path.exists():
            paths.append(file_path)

    return paths


def read_team_memory(project_root: str | Path = ".") -> str:
    """Read all team memory files and combine them."""
    paths = get_team_memory_paths(project_root)
    if not paths:
        return ""

    sections: list[str] = ["## Team Memory Context"]
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8")
            sections.append(f"\n### From {path.name}\n{content}")
        except Exception as exc:
            logger.warning("Failed to read team memory %s: %s", path, exc)

    return "\n".join(sections)


def write_team_memory_entry(
    project_root: str | Path = ".",
    section: str = "## Team Memory",
    entry: str = "",
) -> bool:
    """Add an entry to the team memory file."""
    paths = get_team_memory_paths(project_root)
    if not paths:
        logger.info("No team memory file found, skipping write")
        return False

    target = paths[0]
    try:
        existing = target.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n### {timestamp}\n{entry}\n"
        target.write_text(existing + new_entry, encoding="utf-8")
        logger.info("Added entry to team memory: %s", target.name)
        return True
    except Exception as exc:
        logger.error("Failed to write team memory: %s", exc)
        return False


def build_team_memory_prompt(project_root: str | Path = ".") -> str:
    """Build the team memory section for system prompt."""
    content = read_team_memory(project_root)
    if not content:
        return ""

    return f"\n{content}\n"


def scan_team_memory_sections(content: str) -> dict[str, list[str]]:
    """Parse team memory content into sections."""
    sections: dict[str, list[str]] = {}
    current_section = "General"
    current_items: list[str] = []

    for line in content.splitlines():
        is_section = any(sec in line for sec in TEAM_MEMORY_SECTIONS)
        if is_section:
            if current_items:
                sections[current_section] = current_items
            current_section = line.strip().lstrip("# ")
            current_items = []
        elif line.strip().startswith("-") or line.strip().startswith("*"):
            item = line.lstrip("-*").strip()
            if item:
                current_items.append(item)

    if current_items:
        sections[current_section] = current_items

    return sections


def list_team_memory_entries(project_root: str | Path = ".") -> list[MemoryEntry]:
    """Parse team memory files and return structured MemoryEntry list (scope=TEAM).

    Entries produced here are guaranteed to carry scope=TEAM so they cannot
    contaminate user or repo scopes.
    """
    content = read_team_memory(project_root)
    if not content:
        return []

    entries: list[MemoryEntry] = []
    sections = scan_team_memory_sections(content)
    for section_name, items in sections.items():
        for item in items:
            if len(item) < 10:
                continue
            keywords = extract_keywords(item, top_n=8)
            entry = MemoryEntry(
                id=f"team_{uuid.uuid4().hex[:8]}",
                type=MemoryType.PROJECT,
                scope=MemoryScope.TEAM,
                title=item[:60] + ("..." if len(item) > 60 else ""),
                content=item,
                keywords=keywords,
                metadata=MemoryMetadata(
                    tags=["team", section_name.lower()[:20]],
                ),
            )
            entries.append(entry)
    logger.debug("Loaded %d team memory entries from %s", len(entries), project_root)
    return entries


def create_team_memory_template() -> str:
    """Create a template for new team memory files."""
    return """# Team Memory

This file contains shared knowledge and context for the team.

## Team Context

- Add team-wide context here

## Team Preferences

- Coding standards
- Communication preferences
- Workflow guidelines

## Shared Knowledge

- Architectural decisions
- Important contacts
- Project-specific information

## Onboarding

- Information for new team members
- Getting started guides

---
Last updated: {timestamp}
""".format(timestamp=datetime.now().strftime("%Y-%m-%d"))
