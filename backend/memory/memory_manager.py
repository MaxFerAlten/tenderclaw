"""Memory Manager — multi-scope memory orchestration for conversation injection.

Supports four scopes: user (cross-repo), repo (per-project), team (shared per-repo),
session (ephemeral). Provides save/search/auto-save APIs wired into session lifecycle.

Usage:
    from backend.memory.memory_manager import memory_manager

    # Save a new entry
    memory_manager.save_memory(MemoryScope.REPO, entry)

    # Search with scope filter
    results = memory_manager.search_memory("authentication", scope=MemoryScope.REPO)

    # Build prompt context (called by session at start of turn)
    block = memory_manager.build_context_for_prompt(messages, project_root=cwd)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.memory.keyword_extractor import extract_keywords
from backend.memory.memory_types import MemoryEntry, MemoryIndex, MemoryMetadata, MemoryScope, MemoryType

logger = logging.getLogger("tenderclaw.memory.memory_manager")

# Number of recent messages to include in keyword extraction
_CONTEXT_WINDOW = 4

# Per-scope persistence paths (relative to project root)
_SCOPE_DIRS: dict[MemoryScope, str] = {
    MemoryScope.USER: "~/.tenderclaw/memory/user",
    MemoryScope.REPO: ".tenderclaw/memory/repo",
    MemoryScope.TEAM: ".tenderclaw/memory/team",
    MemoryScope.SESSION: ".tenderclaw/memory/session",
}

_INDEX_FILENAME = "index.json"


class MemoryManager:
    """Orchestrates multi-scope memory: save, search, prompt injection, auto-save."""

    def __init__(self) -> None:
        # In-memory indices per scope (lazy-loaded)
        self._indices: dict[MemoryScope, MemoryIndex] = {}

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _scope_dir(self, scope: MemoryScope, project_root: str | Path = ".") -> Path:
        template = _SCOPE_DIRS[scope]
        if template.startswith("~"):
            return Path(template).expanduser()
        return Path(project_root) / template

    def _index_path(self, scope: MemoryScope, project_root: str | Path = ".") -> Path:
        return self._scope_dir(scope, project_root) / _INDEX_FILENAME

    # ------------------------------------------------------------------
    # Index load/save
    # ------------------------------------------------------------------

    def _load_index(self, scope: MemoryScope, project_root: str | Path = ".") -> MemoryIndex:
        idx_path = self._index_path(scope, project_root)
        if idx_path.exists():
            try:
                data = json.loads(idx_path.read_text(encoding="utf-8"))
                return MemoryIndex.model_validate(data)
            except Exception as exc:
                logger.warning("Corrupted index %s, starting fresh: %s", idx_path, exc)
        return MemoryIndex()

    def _save_index(self, scope: MemoryScope, index: MemoryIndex, project_root: str | Path = ".") -> None:
        idx_path = self._index_path(scope, project_root)
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(index.model_dump_json(indent=2), encoding="utf-8")

    def get_index(self, scope: MemoryScope, project_root: str | Path = ".") -> MemoryIndex:
        """Return the index for a scope, loading from disk if not cached."""
        if scope not in self._indices:
            self._indices[scope] = self._load_index(scope, project_root)
        return self._indices[scope]

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_memory(
        self,
        scope: MemoryScope,
        entry: MemoryEntry,
        project_root: str | Path = ".",
    ) -> None:
        """Persist a memory entry under the given scope."""
        entry.scope = scope
        if not entry.id:
            entry.id = f"mem_{scope.value}_{uuid.uuid4().hex[:8]}"
        index = self.get_index(scope, project_root)
        index.add_entry(entry)
        index.last_scan = datetime.now()
        self._save_index(scope, index, project_root)
        logger.debug("Saved memory entry %s to scope=%s", entry.id, scope.value)

    def save_text(
        self,
        scope: MemoryScope,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT,
        tags: list[str] | None = None,
        project_root: str | Path = ".",
    ) -> MemoryEntry:
        """Create and save a memory entry from plain text."""
        keywords = extract_keywords(content, top_n=10)
        title = content[:60] + ("..." if len(content) > 60 else "")
        entry = MemoryEntry(
            id=f"mem_{scope.value}_{uuid.uuid4().hex[:8]}",
            type=memory_type,
            scope=scope,
            title=title,
            content=content,
            keywords=keywords,
            metadata=MemoryMetadata(tags=tags or []),
        )
        self.save_memory(scope, entry, project_root)
        return entry

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_memory(
        self,
        query: str,
        scope: MemoryScope | None = None,
        limit: int = 10,
        project_root: str | Path = ".",
    ) -> list[MemoryEntry]:
        """Search memory entries, optionally restricted to a scope."""
        keywords = extract_keywords(query, top_n=8)

        scopes_to_search: list[MemoryScope] = (
            [scope] if scope else list(MemoryScope)
        )

        results: list[MemoryEntry] = []
        for s in scopes_to_search:
            index = self.get_index(s, project_root)
            hits = index.search_by_scope(query, scope=s, keywords=keywords)
            results.extend(hits)

        results.sort(key=lambda e: e.relevance_score, reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Prompt injection
    # ------------------------------------------------------------------

    def build_context_for_prompt(
        self,
        messages: list[dict[str, Any]],
        project_root: str | Path = ".",
        limit: int = 5,
        scopes: list[MemoryScope] | None = None,
    ) -> str:
        """Build a formatted memory block for system prompt injection.

        Searches user + repo + team scopes by default (not session, which is ephemeral).
        """
        if not messages:
            return ""

        window = messages[-_CONTEXT_WINDOW:]
        texts: list[str] = []
        for msg in window:
            content = msg.get("content", "")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))

        composite = " ".join(texts).strip()
        if not composite:
            return ""

        search_scopes = scopes or [MemoryScope.USER, MemoryScope.REPO, MemoryScope.TEAM]
        all_results: list[MemoryEntry] = []
        for s in search_scopes:
            hits = self.search_memory(composite, scope=s, limit=limit, project_root=project_root)
            all_results.extend(hits)

        all_results.sort(key=lambda e: e.relevance_score, reverse=True)
        top = all_results[:limit]

        if not top:
            # Fallback: try wisdom store
            return self._fallback_wisdom(composite, limit)

        return _format_for_prompt(top)

    def _fallback_wisdom(self, query: str, limit: int) -> str:
        """Fall back to the wisdom store when no scoped memory is found."""
        try:
            from backend.memory.wisdom import wisdom_store
        except ImportError:
            return ""
        keywords = extract_keywords(query, top_n=12)
        try:
            items = wisdom_store.find_relevant(" ".join(keywords), limit=limit)
        except Exception as exc:
            logger.warning("Wisdom retrieval failed: %s", exc)
            return ""
        if not items:
            return ""
        lines = ["## Relevant Past Patterns"]
        for item in items:
            tag_str = ", ".join(item.tags[:3]) if item.tags else ""
            line = f"- [{item.task_type}] {item.description}: {item.solution_pattern}"
            if tag_str:
                line += f" (tags: {tag_str})"
            lines.append(line)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Auto-save (called by session at end of turn)
    # ------------------------------------------------------------------

    def auto_save_signals(
        self,
        signals: list[MemoryEntry],
        project_root: str | Path = ".",
    ) -> int:
        """Persist extracted signal entries. Returns count saved."""
        saved = 0
        for entry in signals:
            try:
                self.save_memory(entry.scope, entry, project_root)
                saved += 1
            except Exception as exc:
                logger.warning("Failed to auto-save signal %s: %s", entry.id, exc)
        logger.info("Auto-saved %d memory signals", saved)
        return saved

    # ------------------------------------------------------------------
    # Invalidate cache (call when switching project_root)
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        self._indices.clear()


def _format_for_prompt(entries: list[MemoryEntry]) -> str:
    """Serialize memory entries into a compact markdown block."""
    lines = ["## Relevant Memory"]
    for entry in entries:
        scope_tag = f"[{entry.scope.value.upper()}:{entry.type.value}]"
        tag_str = (", ".join(entry.metadata.tags[:3]) if entry.metadata.tags else "")
        line = f"- {scope_tag} **{entry.title}**"
        if tag_str:
            line += f" ({tag_str})"
        preview = entry.content[:200] + ("..." if len(entry.content) > 200 else "")
        lines.append(line)
        lines.append(f"  {preview}")
    return "\n".join(lines)


# Module-level singleton
memory_manager = MemoryManager()
