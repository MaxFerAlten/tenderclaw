"""Coordinator run behavior tests."""

from __future__ import annotations

import asyncio

from backend.orchestration.coordinator import Coordinator, CoordinatorState
from backend.orchestration.coordinator_runner import ensure_task_trace, run_pending_tasks


def test_run_pending_tasks_routes_and_completes_pending_tasks() -> None:
    coordinator = Coordinator(id="coord_run", name="bug hunt")
    bug_task = coordinator.add_task("find bug")
    regression_task = coordinator.add_task("no regration test")

    summary = asyncio.run(run_pending_tasks(coordinator))

    assert summary["status"] == "completed"
    assert summary["completed"] == 2
    assert summary["failed"] == 0
    assert coordinator.state == CoordinatorState.IDLE

    assert bug_task.status == "completed"
    assert bug_task.assignee == "fixer"
    assert bug_task.result is not None
    assert "oracle -> metis -> fixer" in bug_task.result

    assert regression_task.status == "completed"
    assert regression_task.assignee == "fixer"
    assert regression_task.result is not None
    assert "regression coverage" in regression_task.result


def test_run_pending_tasks_records_visible_trace_per_task() -> None:
    coordinator = Coordinator(id="coord_trace", name="visible work")
    task = coordinator.add_task("find bug")

    summary = asyncio.run(run_pending_tasks(coordinator))

    traces = summary["task_traces"]
    assert isinstance(traces, dict)
    task_trace = traces[task.id]
    assert [event["stage"] for event in task_trace] == [
        "intent_gate",
        "planning",
        "assignment",
        "execution",
        "verification",
    ]
    assert task_trace[0]["agent"] == "coordinator"
    assert "fix" in task_trace[0]["detail"]
    assert task_trace[2]["agent"] == "fixer"
    assert "assigned" in task_trace[2]["detail"].lower()
    assert "local coordinator run" in task_trace[3]["detail"].lower()


def test_run_pending_tasks_skips_already_completed_tasks() -> None:
    coordinator = Coordinator(id="coord_skip", name="mixed")
    completed = coordinator.add_task("already done")
    pending = coordinator.add_task("write documentation")
    coordinator.complete_task(completed.id, "keep this result")

    summary = asyncio.run(run_pending_tasks(coordinator))

    assert summary["completed"] == 1
    assert summary["skipped"] == 1
    assert completed.status == "completed"
    assert completed.result == "keep this result"
    assert pending.status == "completed"
    assert pending.assignee == "scribe"


def test_ensure_task_trace_reconstructs_completed_task_trace() -> None:
    coordinator = Coordinator(id="coord_reconstruct", name="old run")
    task = coordinator.add_task("find bug")
    coordinator.assign_task(task.id, "fixer")
    coordinator.complete_task(task.id, "Coordinator pipeline completed: oracle -> metis -> fixer.")

    trace = ensure_task_trace(task)

    assert len(trace) == 5
    assert trace[0]["stage"] == "intent_gate"
    assert trace[2]["agent"] == "fixer"
    assert "reconstructed" in trace[3]["detail"].lower()


def test_run_pending_tasks_returns_idle_summary_when_nothing_is_pending() -> None:
    coordinator = Coordinator(id="coord_idle", name="empty")

    summary = asyncio.run(run_pending_tasks(coordinator))

    assert summary["status"] == "idle"
    assert summary["completed"] == 0
    assert summary["skipped"] == 0
    assert summary["progress"]["percent"] == 0
