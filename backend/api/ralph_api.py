"""Ralph mode API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path

router = APIRouter(prefix="/ralph", tags=["ralph"])


class RalphStatus(BaseModel):
    active: bool
    iteration: int
    phase: str
    task_slug: str


@router.get("/status/{task_slug}")
async def get_status(task_slug: str) -> RalphStatus:
    """Get Ralph execution status for a task."""
    from backend.core.ralph_state import RalphStateManager

    manager = RalphStateManager(Path(".tenderclaw/state"))
    state = manager.load(task_slug)
    if not state:
        return RalphStatus(active=False, iteration=0, phase="idle", task_slug=task_slug)
    return RalphStatus(
        active=state.active,
        iteration=state.iteration,
        phase=state.current_phase,
        task_slug=state.task_slug,
    )


@router.post("/start/{task_slug}")
async def start_ralph(task_slug: str, context: str = "") -> dict:
    """Start Ralph execution for a task."""
    from backend.core.ralph_state import RalphStateManager

    manager = RalphStateManager(Path(".tenderclaw/state"))
    state = manager.start(task_slug, context)
    return {"status": "started", "iteration": state.iteration}


@router.post("/complete/{task_slug}")
async def complete_ralph(task_slug: str) -> dict:
    """Mark Ralph execution complete."""
    from backend.core.ralph_state import RalphStateManager

    manager = RalphStateManager(Path(".tenderclaw/state"))
    state = manager.load(task_slug)
    if state:
        manager.complete(state)
    return {"status": "complete"}