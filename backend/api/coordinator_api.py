"""Coordinator API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/coordinator", tags=["coordinator"])


class CreateCoordinatorRequest(BaseModel):
    name: str


class AddTaskRequest(BaseModel):
    description: str


class AssignTaskRequest(BaseModel):
    task_id: str
    agent_id: str


class CompleteTaskRequest(BaseModel):
    task_id: str
    result: str


@router.post("")
async def create_coordinator(req: CreateCoordinatorRequest) -> dict[str, Any]:
    """Create a new coordinator."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.create(req.name)
    return {
        "id": coordinator.id,
        "name": coordinator.name,
        "state": coordinator.state.value,
        "tasks": [],
        "progress": coordinator.get_progress(),
    }


@router.get("")
async def list_coordinators() -> list[dict[str, Any]]:
    """List all coordinators."""
    from backend.orchestration.coordinator import CoordinatorManager

    return [
        {
            "id": c.id,
            "name": c.name,
            "state": c.state.value,
            "task_count": len(c.tasks),
            "tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "status": t.status,
                    "assignee": t.assignee,
                    "result": t.result,
                }
                for t in c.tasks
            ],
            "progress": c.get_progress(),
        }
        for c in CoordinatorManager.list_all()
    ]


@router.get("/{coordinator_id}")
async def get_coordinator(coordinator_id: str) -> dict[str, Any]:
    """Get coordinator details."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    return {
        "id": coordinator.id,
        "name": coordinator.name,
        "state": coordinator.state.value,
        "tasks": [
            {
                "id": t.id,
                "description": t.description,
                "status": t.status,
                "assignee": t.assignee,
                "result": t.result,
            }
            for t in coordinator.tasks
        ],
        "progress": coordinator.get_progress(),
    }


@router.post("/{coordinator_id}/tasks")
async def add_task(coordinator_id: str, req: AddTaskRequest) -> dict[str, Any]:
    """Add a task to coordinator."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    task = coordinator.add_task(req.description)
    return {"id": task.id, "description": task.description, "status": task.status}


@router.post("/{coordinator_id}/tasks/{task_id}/assign")
async def assign_task(coordinator_id: str, task_id: str, req: AssignTaskRequest) -> dict[str, Any]:
    """Assign a task to an agent."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    if not coordinator.assign_task(task_id, req.agent_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "assigned"}


@router.post("/{coordinator_id}/tasks/{task_id}/complete")
async def complete_task(coordinator_id: str, task_id: str, req: CompleteTaskRequest) -> dict[str, Any]:
    """Mark task as completed."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    if not coordinator.complete_task(task_id, req.result):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "completed", "progress": coordinator.get_progress()}


@router.delete("/{coordinator_id}")
async def delete_coordinator(coordinator_id: str) -> dict[str, str]:
    """Delete a coordinator."""
    from backend.orchestration.coordinator import CoordinatorManager

    if not CoordinatorManager.delete(coordinator_id):
        raise HTTPException(status_code=404, detail="Coordinator not found")
    return {"status": "deleted"}


class StartTeamRequest(BaseModel):
    team_name: str
    num_workers: int = 3


@router.post("/{coordinator_id}/team/start")
async def start_team(coordinator_id: str, req: StartTeamRequest) -> dict[str, Any]:
    """Start team mode with N workers."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    result = coordinator.start_team_mode(req.team_name, req.num_workers)
    return result


@router.get("/{coordinator_id}/team/status")
async def get_team_status(coordinator_id: str) -> dict[str, Any]:
    """Get team execution status."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    return coordinator.get_team_status()


@router.post("/{coordinator_id}/team/shutdown")
async def shutdown_team(coordinator_id: str) -> dict[str, Any]:
    """Shutdown team mode."""
    from backend.orchestration.coordinator import CoordinatorManager

    coordinator = CoordinatorManager.get(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Coordinator not found")
    return coordinator.shutdown_team()
