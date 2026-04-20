"""Deterministic coordinator execution for pending task lists."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from backend.orchestration.coordinator import CoordinatorState, Task
from backend.orchestration.coordinator_trace import (
    build_task_trace,
    ensure_task_trace,
    failed_trace_event,
    select_task_agent,
    set_task_trace,
    verification_event,
)

if TYPE_CHECKING:
    from backend.orchestration.coordinator import Coordinator


RunSummary = dict[str, object]


async def run_pending_tasks(coordinator: Coordinator) -> RunSummary:
    """Run every pending task through the coordinator's local pipeline.

    This is intentionally deterministic: it updates the board, assigns the
    appropriate role, and records the handoff/result without requiring a model
    call. Full agent-backed execution can sit behind this same endpoint later.
    """
    pending = coordinator.get_pending_tasks()
    skipped = len([task for task in coordinator.tasks if task.status != "pending"])
    if not pending:
        return _summary(coordinator, status="idle", completed=0, failed=0, skipped=skipped, assignments=[])

    previous_state = coordinator.state
    coordinator.state = CoordinatorState.ORCHESTRATING
    assignments: list[dict[str, str]] = []
    completed = 0
    failed = 0

    for task in pending:
        agent = select_task_agent(task.description)
        trace = build_task_trace(task, agent)
        set_task_trace(task.id, trace)
        assignments.append({"task_id": task.id, "agent": agent})
        try:
            coordinator.assign_task(task.id, agent)
            await asyncio.sleep(0)
            result = build_task_result(task, agent)
            coordinator.complete_task(task.id, result)
            trace.append(verification_event(task, agent))
            set_task_trace(task.id, trace)
            completed += 1
        except Exception as exc:
            task.status = "failed"
            task.result = f"Coordinator run failed: {type(exc).__name__}: {exc}"
            trace.append(failed_trace_event(task.result))
            set_task_trace(task.id, trace)
            failed += 1

    coordinator.state = previous_state if previous_state == CoordinatorState.TEAM_MODE else CoordinatorState.IDLE
    status = "completed" if failed == 0 else "failed"
    return _summary(
        coordinator,
        status=status,
        completed=completed,
        failed=failed,
        skipped=skipped,
        assignments=assignments,
    )


def build_task_result(task: Task, agent: str) -> str:
    """Create the result text shown in the coordinator UI."""
    focus = {
        "fixer": "bug diagnosis, minimal patching, and regression coverage",
        "scribe": "documentation update and user-facing clarity",
        "sentinel": "security review and risk triage",
        "explorer": "codebase search and evidence gathering",
        "metis": "implementation strategy and gap analysis",
        "sisyphus": "direct execution with verification",
    }[agent]
    return f"Coordinator routing completed: oracle -> metis -> {agent}. Focus: {focus}."


def _summary(
    coordinator: Coordinator,
    *,
    status: str,
    completed: int,
    failed: int,
    skipped: int,
    assignments: list[dict[str, str]],
) -> RunSummary:
    return {
        "status": status,
        "coordinator_id": coordinator.id,
        "state": coordinator.state.value,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "assignments": assignments,
        "task_traces": {
            task.id: ensure_task_trace(task)
            for task in coordinator.tasks
            if ensure_task_trace(task)
        },
        "progress": coordinator.get_progress(),
    }
