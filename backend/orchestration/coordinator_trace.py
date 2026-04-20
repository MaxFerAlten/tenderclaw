"""Visible task traces for coordinator runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from backend.orchestration.coordinator import Task


class TaskTraceEvent(TypedDict):
    stage: str
    agent: str
    title: str
    detail: str


_task_traces: dict[str, list[TaskTraceEvent]] = {}


def select_task_agent(description: str) -> str:
    """Choose the role that should own a task."""
    text = description.lower()
    if _contains_any(text, ("security", "secret", "auth", "permission", "vulnerability")):
        return "sentinel"
    if _contains_any(text, ("bug", "fix", "broken", "failing", "regression", "regration", "test")):
        return "fixer"
    if _contains_any(text, ("doc", "readme", "guide", "changelog", "write-up")):
        return "scribe"
    if _contains_any(text, ("search", "find", "grep", "inspect", "trace")):
        return "explorer"
    if _contains_any(text, ("plan", "design", "architecture", "strategy")):
        return "metis"
    return "sisyphus"


def set_task_trace(task_id: str, trace: list[TaskTraceEvent]) -> None:
    _task_traces[task_id] = trace


def ensure_task_trace(task: Task) -> list[TaskTraceEvent]:
    """Return a task trace, reconstructing one for older completed tasks."""
    if task.id in _task_traces:
        return get_task_trace(task.id)

    if task.status == "pending":
        return []

    agent = task.assignee or select_task_agent(task.description)
    trace = build_task_trace(task, agent)
    trace[3] = {
        "stage": "execution",
        "agent": agent,
        "title": "Previous result",
        "detail": "Reconstructed from saved task state; the original live trace was not recorded.",
    }
    trace.append(verification_event(task, agent))
    set_task_trace(task.id, trace)
    return get_task_trace(task.id)


def get_task_trace(task_id: str) -> list[TaskTraceEvent]:
    """Return the recorded visible trace for a task."""
    return list(_task_traces.get(task_id, []))


def build_task_trace(task: Task, agent: str) -> list[TaskTraceEvent]:
    intent = _intent_label(agent)
    return [
        {
            "stage": "intent_gate",
            "agent": "coordinator",
            "title": "Intent classified",
            "detail": f"Classified as {intent} from task text: {task.description}",
        },
        {
            "stage": "planning",
            "agent": "metis",
            "title": "Execution path selected",
            "detail": f"Plan: inspect context, route ownership, prepare {agent} handoff, verify board state.",
        },
        {
            "stage": "assignment",
            "agent": agent,
            "title": "Owner assigned",
            "detail": f"Assigned to {agent} because {_agent_reason(agent)}",
        },
        {
            "stage": "execution",
            "agent": agent,
            "title": "Local coordinator run",
            "detail": "Local coordinator run updated task routing and result text; no model call was made from this board.",
        },
    ]


def verification_event(task: Task, agent: str) -> TaskTraceEvent:
    return {
        "stage": "verification",
        "agent": "coordinator",
        "title": "Board state verified",
        "detail": f"Task status is {task.status}; result is visible; final owner is {agent}.",
    }


def failed_trace_event(result: str) -> TaskTraceEvent:
    return {
        "stage": "verification",
        "agent": "coordinator",
        "title": "Run failed",
        "detail": result,
    }


def _intent_label(agent: str) -> str:
    return {
        "fixer": "fix",
        "scribe": "documentation",
        "sentinel": "security review",
        "explorer": "research",
        "metis": "planning",
        "sisyphus": "implementation",
    }[agent]


def _agent_reason(agent: str) -> str:
    return {
        "fixer": "the task mentions bug, fix, failing, regression, or tests",
        "scribe": "the task asks for documentation or writing",
        "sentinel": "the task contains security-sensitive wording",
        "explorer": "the task asks to search, inspect, or trace code",
        "metis": "the task is primarily planning or architecture",
        "sisyphus": "the task is a general execution request",
    }[agent]


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)
