"""Hook engine — priority-ordered lifecycle hook execution.

Hooks fire at defined lifecycle points (session, turn, tool, message).
They run in priority order, and a handler can bail out to stop the chain.

Sprint 6: added ConflictResolution strategies for MODIFY actions.
Handlers can declare LAST_WIN (default), FIRST_WIN, or MERGE to control how
their modifications interact with data already written by earlier hooks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from backend.schemas.hooks import (
    HookAction,
    HookEvent,
    HookPoint,
    HookResult,
    HookTier,
)

logger = logging.getLogger("tenderclaw.hooks.engine")

# Type alias for async hook handlers
HookHandler = Callable[[HookEvent], Awaitable[HookResult]]

# Priority values for each tier (lower = runs first)
_TIER_PRIORITY: dict[HookTier, int] = {
    HookTier.CORE: 0,
    HookTier.CONTINUATION: 100,
    HookTier.SKILL: 200,
    HookTier.TRANSFORM: 300,
}


class ConflictResolution(str, Enum):
    """Strategy for resolving key conflicts when a MODIFY hook writes data
    that overlaps with keys already present in the event payload.

    LAST_WIN  — (default) later hook's value overwrites the existing value.
    FIRST_WIN — existing value is preserved; the new value is silently dropped.
    MERGE     — lists are concatenated, dicts are shallow-merged (new keys added,
                 existing keys updated), scalars fall back to LAST_WIN.
    """

    LAST_WIN = "last_win"
    FIRST_WIN = "first_win"
    MERGE = "merge"


def _apply_modify(event: HookEvent, result: HookResult, strategy: ConflictResolution) -> None:
    """Apply a MODIFY result's data onto *event.data* using *strategy*."""
    for key, new_val in result.data.items():
        if key not in event.data:
            event.data[key] = new_val
            continue

        existing = event.data[key]

        if strategy == ConflictResolution.LAST_WIN:
            event.data[key] = new_val

        elif strategy == ConflictResolution.FIRST_WIN:
            pass  # keep existing — do nothing

        elif strategy == ConflictResolution.MERGE:
            if isinstance(existing, list) and isinstance(new_val, list):
                event.data[key] = existing + new_val
            elif isinstance(existing, dict) and isinstance(new_val, dict):
                event.data[key] = {**existing, **new_val}
            else:
                # Incompatible types — fall back to LAST_WIN
                event.data[key] = new_val


@dataclass
class HookEntry:
    """A registered hook handler with metadata."""

    name: str
    point: HookPoint
    handler: HookHandler
    tier: HookTier = HookTier.SKILL
    priority: int = 0  # Within-tier priority (lower = earlier)
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WIN

    @property
    def effective_priority(self) -> int:
        """Combined priority: tier base + within-tier offset."""
        return _TIER_PRIORITY.get(self.tier, 200) + self.priority


class HookRegistry:
    """Registry and runner for lifecycle hooks."""

    def __init__(self) -> None:
        self._hooks: dict[HookPoint, list[HookEntry]] = {}

    def register(
        self,
        name: str,
        point: HookPoint,
        handler: HookHandler,
        tier: HookTier = HookTier.SKILL,
        priority: int = 0,
        conflict_resolution: ConflictResolution = ConflictResolution.LAST_WIN,
    ) -> None:
        """Register a hook handler for a lifecycle point.

        Args:
            name:                Unique name for this hook.
            point:               Lifecycle point to attach to.
            handler:             Async callable receiving HookEvent, returning HookResult.
            tier:                Priority tier (core > continuation > skill > transform).
            priority:            Within-tier ordering (lower runs first).
            conflict_resolution: How MODIFY data merges with existing event.data.
        """
        entry = HookEntry(
            name=name,
            point=point,
            handler=handler,
            tier=tier,
            priority=priority,
            conflict_resolution=conflict_resolution,
        )

        if point not in self._hooks:
            self._hooks[point] = []
        self._hooks[point].append(entry)
        self._hooks[point].sort(key=lambda e: e.effective_priority)
        logger.debug("Hook registered: %s at %s (tier=%s, conflict=%s)", name, point.value, tier.value, conflict_resolution.value)

    def unregister(self, name: str) -> None:
        """Remove all hooks with the given name."""
        for point, entries in self._hooks.items():
            self._hooks[point] = [e for e in entries if e.name != name]

    async def run_hooks(self, point: HookPoint, event: HookEvent) -> HookResult:
        """Run all hooks for a lifecycle point in priority order.

        If any hook returns BAIL, execution stops and that result is returned.
        If a hook returns MODIFY, its data is merged into the event for
        subsequent hooks using the hook's declared ConflictResolution strategy.

        Returns:
            The last HookResult (or CONTINUE with empty data if no hooks ran).
        """
        entries = self._hooks.get(point, [])
        if not entries:
            return HookResult(action=HookAction.CONTINUE)

        last_result = HookResult(action=HookAction.CONTINUE)

        for entry in entries:
            try:
                result = await entry.handler(event)
            except Exception as exc:
                logger.error("Hook %s raised: %s", entry.name, exc)
                continue

            last_result = result

            if result.action == HookAction.BAIL:
                logger.info("Hook %s bailed at %s: %s", entry.name, point.value, result.reason)
                return result

            if result.action == HookAction.MODIFY:
                _apply_modify(event, result, entry.conflict_resolution)

        return last_result

    def list_hooks(self, point: HookPoint | None = None) -> list[str]:
        """List registered hook names, optionally filtered by point."""
        if point is not None:
            return [e.name for e in self._hooks.get(point, [])]
        return [e.name for entries in self._hooks.values() for e in entries]


# Module-level instance
hook_registry = HookRegistry()
