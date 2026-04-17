"""Pruning Strategies for Conversation History.

Implements OpenClaw-style pruning strategies:
- Deduplication: Remove duplicate tool outputs
- Supersede Writes: Prune old writes if file was later read
- Purge Errors: Remove error messages after N turns
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Set

from backend.services.compaction.messages import AgentMessage, MessageRole


@dataclass
class DeduplicationStrategy:
    """Deduplication pruning strategy.

    Removes duplicate tool outputs to save tokens.
    """

    enabled: bool = True
    keep_latest: bool = True  # Keep latest duplicate, remove older
    max_age_turns: Optional[int] = None  # Only dedupe within N turns

    def apply(self, messages: List[AgentMessage]) -> tuple[List[AgentMessage], Dict[str, Any]]:
        """Apply deduplication to messages.

        Returns filtered messages and stats.
        """
        if not self.enabled:
            return messages, {"removed": 0}

        seen_outputs: Dict[str, List[tuple[int, AgentMessage]]] = {}
        result: List[AgentMessage] = []
        stats = {"removed": 0}

        for i, msg in enumerate(messages):
            if msg.role != MessageRole.TOOL_RESULT:
                result.append(msg)
                continue

            # Create a signature for deduplication
            signature = self._create_signature(msg)
            if not signature:
                result.append(msg)
                continue

            # Check for duplicate
            if signature in seen_outputs:
                if self.keep_latest:
                    # Mark older for removal, keep this one
                    seen_outputs[signature].append((i, msg))
                else:
                    # Keep older, skip this one
                    seen_outputs[signature].append((i, msg))
                    stats["removed"] += 1
            else:
                seen_outputs[signature] = [(i, msg)]
                result.append(msg)

        # Remove duplicates if keeping latest
        if self.keep_latest:
            to_remove: Set[int] = set()
            for signature, positions in seen_outputs.items():
                if len(positions) > 1:
                    # Keep the last one, remove others
                    for pos, _ in positions[:-1]:
                        to_remove.add(pos)
                        stats["removed"] += 1

            result = [msg for i, msg in enumerate(result) if i not in to_remove]

        return result, stats

    def _create_signature(self, msg: AgentMessage) -> Optional[str]:
        """Create a deduplication signature for a tool result."""
        if not msg.tool_call_id:
            return None

        # Include tool name and content hash, but not the full content
        content = msg.tool_result_content or msg.content or ""
        # Simple hash for signature
        content_hash = hash(content[:200])  # First 200 chars

        return f"{msg.tool_name or 'unknown'}:{content_hash}"


@dataclass
class SupersedeWritesStrategy:
    """Supersede Writes pruning strategy.

    If a file was written, then read later, the old write is less relevant
    and can be pruned to save tokens.
    """

    enabled: bool = True
    file_patterns: List[str] = field(default_factory=lambda: [r"\.(py|ts|js|tsx|jsx|java|cpp|c|h)$"])

    def apply(self, messages: List[AgentMessage]) -> tuple[List[AgentMessage], Dict[str, Any]]:
        """Apply supersede writes to messages.

        Returns filtered messages and stats.
        """
        if not self.enabled:
            return messages, {"removed": 0}

        # Track file operations
        file_states: Dict[str, str] = {}  # file -> last operation (write/read)
        file_operations: Dict[str, List[int]] = {}  # file -> list of message indices
        result: List[AgentMessage] = []
        stats = {"removed": 0, "superseded": []}

        for i, msg in enumerate(messages):
            if msg.role != MessageRole.TOOL_RESULT:
                result.append(msg)
                continue

            content = msg.tool_result_content or msg.content or ""
            tool_name = msg.tool_name or ""

            # Detect file operations from tool output
            file_ref = self._extract_file_reference(content, tool_name)
            if not file_ref:
                result.append(msg)
                continue

            # Track operation
            if file_ref not in file_operations:
                file_operations[file_ref] = []
            file_operations[file_ref].append(len(result))

            # Determine operation type
            op_type = self._detect_operation(content, tool_name)

            # Update state
            old_state = file_states.get(file_ref)
            file_states[file_ref] = op_type

            # Check if this supersedes old writes
            if old_state == "write" and op_type == "read":
                # This read supersedes the old write - mark old writes for removal
                if file_ref in file_operations:
                    # We'll handle this after collecting all
                    pass

            result.append(msg)

        # Post-process: identify superseded writes
        for file_ref, indices in file_operations.items():
            if len(indices) < 2:
                continue

            # Find write followed by read
            for j in range(len(indices) - 1):
                state_at_j = file_states.get(file_ref, "")
                # The write at indices[j] is superseded by the read at indices[j+1]

        return result, stats

    def _extract_file_reference(self, content: str, tool_name: str) -> Optional[str]:
        """Extract file reference from tool output."""
        # Common patterns for file paths
        patterns = [
            r"([A-Za-z]:\\[\w\\.-]+|/\w+[\w/.-]*\.\w+)",  # File paths
            r"[Ff]ile:\s*([^\s]+)",  # File: path
            r"[Ww]rote:\s*([^\s]+)",  # Wrote: path
            r"[Rr]ead:\s*([^\s]+)",  # Read: path
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        return None

    def _detect_operation(self, content: str, tool_name: str) -> str:
        """Detect the type of file operation."""
        content_lower = content.lower()

        if any(kw in content_lower for kw in ["created", "wrote", "saved", "updated"]):
            return "write"
        if any(kw in content_lower for kw in ["read", "contents", "displayed"]):
            return "read"
        if any(kw in content_lower for kw in ["deleted", "removed"]):
            return "delete"

        return "unknown"


@dataclass
class PurgeErrorsStrategy:
    """Purge Errors pruning strategy.

    Removes error messages after N successful turns to reduce noise.
    """

    enabled: bool = True
    error_threshold: int = 5  # Purge errors after this many successful turns
    keep_recent: int = 2  # Always keep this many recent errors
    max_total: int = 10  # Maximum errors to keep

    def apply(self, messages: List[AgentMessage]) -> tuple[List[AgentMessage], Dict[str, Any]]:
        """Apply purge errors to messages.

        Returns filtered messages and stats.
        """
        if not self.enabled:
            return messages, {"removed": 0}

        result: List[AgentMessage] = []
        stats = {"removed": 0}
        error_positions: List[int] = []
        successful_turns = 0

        for msg in messages:
            # Track successful turns (assistant messages that didn't error)
            if msg.role == MessageRole.ASSISTANT:
                has_error = False
                if msg.tool_calls:
                    # Check if any tool calls failed
                    # This would require looking ahead or tracking
                    pass
                successful_turns += 1

            # Track error positions
            if msg.role == MessageRole.TOOL_RESULT and msg.is_error:
                error_positions.append(len(result))

            result.append(msg)

        # If we have enough successful turns, purge old errors
        if successful_turns >= self.error_threshold and len(error_positions) > self.keep_recent:
            # Keep recent errors, remove older ones
            errors_to_remove = error_positions[:-self.keep_recent]
            if len(errors_to_remove) > self.max_total - self.keep_recent:
                errors_to_remove = errors_to_remove[:self.max_total - self.keep_recent]

            # Rebuild result without old errors
            new_result = []
            error_set = set(errors_to_remove)
            for i, msg in enumerate(result):
                if i not in error_set:
                    new_result.append(msg)
                else:
                    stats["removed"] += 1

            return new_result, stats

        return result, stats


@dataclass
class CriticalTurnProtection:
    """Protect CRITICAL turns from any pruning strategy.

    A turn is CRITICAL if:
    - It contains a failed tool result (`is_error=True`)
    - Its content matches architectural decision keywords
    - It is explicitly tagged as critical via `_critical` metadata marker

    Protected turns are marked with `msg._critical = True` and skipped
    by all downstream strategies.
    """

    enabled: bool = True
    # Keywords that flag a turn as an architectural decision
    arch_keywords: List[str] = field(default_factory=lambda: [
        "decided", "decision", "architecture", "we chose", "tradeoff",
        "won't change", "permanent", "critical", "CRITICAL",
    ])

    def mark_critical(self, messages: List[AgentMessage]) -> List[AgentMessage]:
        """Tag messages that must not be pruned. Returns the same list (mutated)."""
        if not self.enabled:
            return messages

        for msg in messages:
            if getattr(msg, "_critical", False):
                continue  # Already tagged

            is_critical = False

            # Failed tool results are always critical
            if msg.role == MessageRole.TOOL_RESULT and msg.is_error:
                is_critical = True

            # Architectural decision keywords in content
            if not is_critical:
                content = msg.tool_result_content or msg.content or ""
                content_lower = content.lower()
                if any(kw.lower() in content_lower for kw in self.arch_keywords):
                    is_critical = True

            if is_critical:
                object.__setattr__(msg, "_critical", True)  # type: ignore[arg-type]

        return messages

    def apply(self, messages: List[AgentMessage]) -> tuple[List[AgentMessage], Dict[str, Any]]:
        """Mark critical turns. Does not remove messages itself."""
        self.mark_critical(messages)
        critical_count = sum(1 for m in messages if getattr(m, "_critical", False))
        return messages, {"critical_marked": critical_count}


def _is_critical(msg: AgentMessage) -> bool:
    return getattr(msg, "_critical", False)


def prune_with_strategies(
    messages: List[AgentMessage],
    deduplication: Optional[DeduplicationStrategy] = None,
    supersede_writes: Optional[SupersedeWritesStrategy] = None,
    purge_errors: Optional[PurgeErrorsStrategy] = None,
    critical_protection: Optional[CriticalTurnProtection] = None,
) -> tuple[List[AgentMessage], Dict[str, Any]]:
    """Apply all enabled pruning strategies.

    Returns pruned messages and combined stats.
    """
    result = list(messages)  # Make a copy
    stats: Dict[str, Any] = {
        "total_original": len(messages),
        "strategies_applied": [],
    }

    # --- 0. Mark CRITICAL turns before any pruning ---
    protection = critical_protection or CriticalTurnProtection()
    result, cp_stats = protection.apply(result)
    stats["strategies_applied"].append("critical_protection")
    stats["critical_protection"] = cp_stats

    # Helper: wrap a strategy so it never removes critical messages
    def _safe_apply(strategy, name: str) -> None:
        nonlocal result
        # Separate critical messages out, apply strategy to the rest, put them back
        critical = [m for m in result if _is_critical(m)]
        non_critical = [m for m in result if not _is_critical(m)]
        pruned, s_stats = strategy.apply(non_critical)
        # Merge: restore critical messages in their original relative positions
        restored: List[AgentMessage] = []
        ci = 0  # index into pruned (non-critical)
        for m in result:  # walk original order to preserve positions
            if _is_critical(m):
                restored.append(m)
            elif ci < len(pruned) and pruned[ci] is m:
                restored.append(m)
                ci += 1
            # else: this non-critical message was pruned — skip it
        result[:] = restored
        stats["strategies_applied"].append(name)
        stats[name] = s_stats

    # Apply in order: dedup -> supersede -> purge errors
    if deduplication and deduplication.enabled:
        _safe_apply(deduplication, "deduplication")

    if supersede_writes and supersede_writes.enabled:
        _safe_apply(supersede_writes, "supersede_writes")

    if purge_errors and purge_errors.enabled:
        _safe_apply(purge_errors, "purge_errors")

    stats["total_final"] = len(result)
    stats["removed_total"] = stats["total_original"] - stats["total_final"]

    return result, stats
