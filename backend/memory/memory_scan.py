"""Memory Scanner — scan .md files for MEMORY.md system integration."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.memory.memory_types import MemoryEntry, MemoryMetadata, MemoryScope, MemoryType
from backend.memory.keyword_extractor import extract_keywords

logger = logging.getLogger("tenderclaw.memory.scan")

MEMORY_SECTIONS = {
    "# User Preferences": MemoryType.USER,
    "# User Memory": MemoryType.USER,
    "## User Preferences": MemoryType.USER,
    "## User Memory": MemoryType.USER,
    "# Feedback": MemoryType.FEEDBACK,
    "## Feedback": MemoryType.FEEDBACK,
    "# Project Context": MemoryType.PROJECT,
    "## Project Context": MemoryType.PROJECT,
    "# Reference": MemoryType.REFERENCE,
    "## Reference": MemoryType.REFERENCE,
    "# References": MemoryType.REFERENCE,
}

MEMORY_FILE_PATTERNS = [
    "MEMORY.md",
    "memory.md",
    ".memory.md",
    "CONTEXT.md",
    ".context.md",
]


class MemoryScanner:
    """Scans project files for memory entries."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)
        self._section_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        self._entry_pattern = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
        self._tag_pattern = re.compile(r"\[([^\]]+)\]")

    def find_memory_files(self) -> list[Path]:
        """Find all memory-related markdown files in the project."""
        found: list[Path] = []
        for pattern in MEMORY_FILE_PATTERNS:
            found.extend(self.project_root.rglob(pattern))
        return sorted(set(found))

    def scan_file(self, file_path: Path) -> list[MemoryEntry]:
        """Scan a single markdown file and extract memory entries."""
        entries: list[MemoryEntry] = []
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read %s: %s", file_path, exc)
            return entries

        current_section: str | None = None
        current_type = MemoryType.PROJECT
        current_tags: list[str] = []
        line_num = 0

        for line_num, line in enumerate(content.splitlines(), 1):
            section_match = self._section_pattern.match(line)
            if section_match:
                current_section = section_match.group(2).strip()
                current_type = self._detect_type(current_section)
                current_tags = self._extract_tags_from_section(current_section)
                continue

            if line.strip().startswith("-") or line.strip().startswith("*"):
                entry_text = line.lstrip("-*").strip()
                if entry_text and len(entry_text) > 5:
                    entry = self._create_entry(
                        entry_text, current_type, current_tags, str(file_path), line_num
                    )
                    if entry:
                        entries.append(entry)

        logger.info("Scanned %s: found %d entries", file_path.name, len(entries))
        return entries

    def scan_project(self) -> list[MemoryEntry]:
        """Scan all memory files in the project."""
        all_entries: list[MemoryEntry] = []
        for memory_file in self.find_memory_files():
            entries = self.scan_file(memory_file)
            all_entries.extend(entries)
        return all_entries

    def _detect_type(self, section: str) -> MemoryType:
        """Detect memory type from section header."""
        section_lower = section.lower()
        if "user" in section_lower:
            return MemoryType.USER
        if "feedback" in section_lower:
            return MemoryType.FEEDBACK
        if "reference" in section_lower:
            return MemoryType.REFERENCE
        return MemoryType.PROJECT

    def _extract_tags_from_section(self, section: str) -> list[str]:
        """Extract tags from section name."""
        tags = self._tag_pattern.findall(section)
        keywords = extract_keywords(section, top_n=5)
        return list(set(tags + keywords))

    def _create_entry(
        self,
        content: str,
        memory_type: MemoryType,
        tags: list[str],
        source: str,
        line: int,
    ) -> MemoryEntry | None:
        """Create a memory entry from content."""
        if len(content) < 10:
            return None

        keywords = extract_keywords(content, top_n=10)
        title = self._extract_title(content)

        entry_id = self._generate_id(content, line)

        return MemoryEntry(
            id=entry_id,
            type=memory_type,
            title=title,
            content=content,
            keywords=keywords,
            metadata=MemoryMetadata(
                source_file=source,
                line_number=line,
                tags=tags,
                created_at=datetime.now(),
            ),
        )

    def _extract_title(self, content: str) -> str:
        """Extract a title from entry content."""
        clean = content.strip()
        if len(clean) > 60:
            clean = clean[:57] + "..."
        return clean

    def _generate_id(self, content: str, line: int) -> str:
        """Generate a unique ID for an entry."""
        prefix = content[:20].lower().replace(" ", "_")[:20]
        return f"mem_{prefix}_{line}_{datetime.now().strftime('%H%M%S')}"


def score_memory_relevance(entry: MemoryEntry, keywords: list[str], query: str) -> float:
    """Calculate relevance score for a memory entry."""
    score = entry.relevance_score
    query_lower = query.lower()

    if query_lower in entry.title.lower():
        score += 3.0
    if query_lower in entry.content.lower():
        score += 1.5

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in entry.keywords:
            score += 1.0
        if kw_lower in entry.title.lower():
            score += 0.8
        if kw_lower in entry.content.lower():
            score += 0.4
        if kw_lower in entry.metadata.tags:
            score += 1.5

    if entry.metadata.priority > 0:
        score += entry.metadata.priority * 0.5

    entry.relevance_score = score
    return score


def get_scanner(project_root: str = ".") -> MemoryScanner:
    """Get a configured memory scanner."""
    return MemoryScanner(Path(project_root))


# ---------------------------------------------------------------------------
# Signal extraction from conversation transcript
# ---------------------------------------------------------------------------

# Patterns that indicate a learnable signal in user messages
_USER_SIGNAL_PATTERNS: list[tuple[re.Pattern, MemoryType, MemoryScope]] = [
    # Explicit preferences / feedback
    (re.compile(r"\b(always|never|prefer|don't|do not|please|stop|keep)\b", re.I), MemoryType.FEEDBACK, MemoryScope.USER),
    # Project decisions
    (re.compile(r"\b(we use|we are using|the project uses|decided to|we chose|our stack)\b", re.I), MemoryType.PROJECT, MemoryScope.REPO),
    # Team conventions
    (re.compile(r"\b(team|everyone|our convention|standard|policy|agreed)\b", re.I), MemoryType.PROJECT, MemoryScope.TEAM),
    # References
    (re.compile(r"\b(see|check|refer to|documented in|wiki|confluence|jira|linear|notion)\b", re.I), MemoryType.REFERENCE, MemoryScope.REPO),
]

_MIN_SIGNAL_LENGTH = 20
_MAX_SIGNAL_LENGTH = 500


def extract_signals_from_transcript(
    messages: list[dict],
    session_id: str = "",
) -> list[MemoryEntry]:
    """Scan conversation messages and extract learnable memory signals.

    Only inspects user-role messages. Returns a list of MemoryEntry objects
    ready to be persisted via memory_manager.auto_save_signals().
    """
    signals: list[MemoryEntry] = []
    seen_contents: set[str] = set()

    for msg in messages:
        if msg.get("role") != "user":
            continue

        raw_content = msg.get("content", "")
        texts: list[str] = []
        if isinstance(raw_content, str):
            texts = [raw_content]
        elif isinstance(raw_content, list):
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))

        for text in texts:
            text = text.strip()
            if len(text) < _MIN_SIGNAL_LENGTH:
                continue

            # Deduplicate
            fingerprint = text[:80].lower()
            if fingerprint in seen_contents:
                continue

            for pattern, mem_type, scope in _USER_SIGNAL_PATTERNS:
                if pattern.search(text):
                    seen_contents.add(fingerprint)
                    content = text[:_MAX_SIGNAL_LENGTH]
                    keywords = extract_keywords(content, top_n=8)
                    title = content[:60] + ("..." if len(content) > 60 else "")
                    entry_id = f"sig_{scope.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(signals):03d}"
                    signals.append(MemoryEntry(
                        id=entry_id,
                        type=mem_type,
                        scope=scope,
                        title=title,
                        content=content,
                        keywords=keywords,
                        metadata=MemoryMetadata(
                            tags=["auto-extracted", f"session:{session_id[:8]}" if session_id else ""],
                            created_at=datetime.now(),
                        ),
                    ))
                    break  # One signal per text block

    logger.info("Extracted %d signals from transcript (%d messages)", len(signals), len(messages))
    return signals
