"""Wisdom Accumulator — store and retrieve successful coding patterns.

Wisdom items are extracted from successful task completions to
inform the agent in future sessions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("tenderclaw.memory.wisdom")


class WisdomItem(BaseModel):
    """A single piece of accumulated knowledge."""

    id: str
    task_type: str
    description: str
    solution_pattern: str
    success_score: float = 1.0
    created_at: datetime = Field(default_factory=datetime.now)
    usage_count: int = 0


class WisdomStore:
    """Persistent storage for accumulated wisdom."""

    def __init__(self, storage_path: str = ".tenderclaw/wisdom") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._wisdom: list[WisdomItem] = []
        self._load_all()

    def add(self, item: WisdomItem) -> None:
        """Store a new piece of wisdom."""
        self._wisdom.append(item)
        file_path = self.storage_path / f"{item.id}.json"
        file_path.write_text(item.model_dump_json(indent=2))
        logger.info("New wisdom added: %s (%s)", item.description, item.id)

    def find_relevant(self, query: str) -> list[WisdomItem]:
        """Find wisdom items relevant to a task query (simple keyword match for now)."""
        results = []
        for item in self._wisdom:
            if any(q.lower() in item.description.lower() or q.lower() in item.task_type.lower()
                   for q in query.split()):
                results.append(item)
        return results

    def _load_all(self) -> None:
        """Load all wisdom files from disk."""
        for file_path in self.storage_path.glob("*.json"):
            try:
                data = json.loads(file_path.read_text())
                self._wisdom.append(WisdomItem.model_validate(data))
            except Exception as exc:
                logger.error("Failed to load wisdom %s: %s", file_path, exc)


# Module-level instance
wisdom_store = WisdomStore()
