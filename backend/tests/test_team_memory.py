"""Tests — Sprint 1 team memory: scope enforcement, isolation from user memory."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.memory.memory_types import MemoryScope
from backend.memory.team_mem import (
    TEAM_MEMORY_DIRS,
    TEAM_MEMORY_FILES,
    build_team_memory_prompt,
    create_team_memory_template,
    get_team_memory_paths,
    list_team_memory_entries,
    read_team_memory,
    scan_team_memory_sections,
    write_team_memory_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_with_team_memory(tmp_path: Path) -> Path:
    """Create a project directory with a .team/memory/MEMORY.md file."""
    mem_dir = tmp_path / ".team" / "memory"
    mem_dir.mkdir(parents=True)
    content = textwrap.dedent("""\
        # Team Memory

        ## Team Context
        - We are a backend team of 5 engineers
        - Primary stack is Python + FastAPI + PostgreSQL

        ## Team Preferences
        - Always use Black for formatting
        - PR reviews required before merge

        ## Shared Knowledge
        - Auth service is maintained by Alice
        - Staging env is at staging.internal
    """)
    (mem_dir / "MEMORY.md").write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------


class TestGetTeamMemoryPaths:
    def test_finds_file_in_team_dir(self, project_with_team_memory: Path) -> None:
        paths = get_team_memory_paths(project_with_team_memory)
        assert len(paths) >= 1
        assert any("MEMORY.md" in str(p) for p in paths)

    def test_returns_empty_for_project_without_team_dir(self, tmp_path: Path) -> None:
        paths = get_team_memory_paths(tmp_path)
        assert paths == []


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestReadTeamMemory:
    def test_reads_content(self, project_with_team_memory: Path) -> None:
        content = read_team_memory(project_with_team_memory)
        assert "Team Memory Context" in content
        assert "FastAPI" in content

    def test_empty_for_no_team_memory(self, tmp_path: Path) -> None:
        assert read_team_memory(tmp_path) == ""


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


class TestWriteTeamMemory:
    def test_write_appends_entry(self, project_with_team_memory: Path) -> None:
        ok = write_team_memory_entry(
            project_with_team_memory,
            section="## Team Context",
            entry="Bob joined the team as DevOps engineer",
        )
        assert ok is True
        content = read_team_memory(project_with_team_memory)
        assert "Bob" in content


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


class TestScanTeamMemorySections:
    def test_sections_parsed(self, project_with_team_memory: Path) -> None:
        raw = read_team_memory(project_with_team_memory)
        sections = scan_team_memory_sections(raw)
        # Should have some sections with items
        assert isinstance(sections, dict)
        all_items = [item for items in sections.values() for item in items]
        assert len(all_items) >= 1

    def test_returns_empty_for_empty_content(self) -> None:
        sections = scan_team_memory_sections("")
        assert sections == {} or all(len(v) == 0 for v in sections.values())


# ---------------------------------------------------------------------------
# list_team_memory_entries — scope enforcement
# ---------------------------------------------------------------------------


class TestListTeamMemoryEntries:
    def test_all_entries_have_team_scope(self, project_with_team_memory: Path) -> None:
        entries = list_team_memory_entries(project_with_team_memory)
        assert len(entries) >= 1
        for entry in entries:
            assert entry.scope == MemoryScope.TEAM, (
                f"Entry {entry.id!r} has scope={entry.scope!r}, expected TEAM"
            )

    def test_entries_have_team_tag(self, project_with_team_memory: Path) -> None:
        entries = list_team_memory_entries(project_with_team_memory)
        for entry in entries:
            assert "team" in entry.metadata.tags

    def test_no_user_scope_in_team_entries(self, project_with_team_memory: Path) -> None:
        entries = list_team_memory_entries(project_with_team_memory)
        assert not any(e.scope == MemoryScope.USER for e in entries)

    def test_no_session_scope_in_team_entries(self, project_with_team_memory: Path) -> None:
        entries = list_team_memory_entries(project_with_team_memory)
        assert not any(e.scope == MemoryScope.SESSION for e in entries)

    def test_returns_empty_for_no_team_memory(self, tmp_path: Path) -> None:
        entries = list_team_memory_entries(tmp_path)
        assert entries == []


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


class TestBuildTeamMemoryPrompt:
    def test_includes_content(self, project_with_team_memory: Path) -> None:
        prompt = build_team_memory_prompt(project_with_team_memory)
        assert "FastAPI" in prompt or "Team Memory" in prompt

    def test_empty_for_no_team_memory(self, tmp_path: Path) -> None:
        assert build_team_memory_prompt(tmp_path) == ""


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


class TestCreateTeamMemoryTemplate:
    def test_template_has_required_sections(self) -> None:
        template = create_team_memory_template()
        assert "Team Context" in template
        assert "Team Preferences" in template
        assert "Shared Knowledge" in template
