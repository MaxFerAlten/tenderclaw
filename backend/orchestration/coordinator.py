"""Coordinator mode for managing multiple agent sessions."""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable
import asyncio
import uuid


class CoordinatorState(str, Enum):
    IDLE = "idle"
    ORCHESTRATING = "orchestrating"
    TEAM_MODE = "team_mode"
    PAUSED = "paused"


@dataclass
class Task:
    id: str
    description: str
    status: str = "pending"
    assignee: str | None = None
    result: str | None = None


@dataclass
class Coordinator:
    id: str
    name: str
    state: CoordinatorState = CoordinatorState.IDLE
    tasks: list[Task] = field(default_factory=list)
    agents: dict[str, str] = field(default_factory=dict)
    results: dict[str, str] = field(default_factory=dict)
    team_name: str | None = None
    num_workers: int = 0

    def add_task(self, description: str) -> Task:
        task = Task(id=str(uuid.uuid4()), description=description)
        self.tasks.append(task)
        return task

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.assignee = agent_id
                task.status = "running"
                return True
        return False

    def complete_task(self, task_id: str, result: str) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.status = "completed"
                task.result = result
                self.results[task_id] = result
                return True
        return False

    def get_pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == "pending"]

    def get_progress(self) -> dict:
        total = len(self.tasks)
        if total == 0:
            return {"total": 0, "completed": 0, "running": 0, "pending": 0, "percent": 0}

        completed = len([t for t in self.tasks if t.status == "completed"])
        running = len([t for t in self.tasks if t.status == "running"])
        pending = len([t for t in self.tasks if t.status == "pending"])

        return {
            "total": total,
            "completed": completed,
            "running": running,
            "pending": pending,
            "percent": int(completed / total * 100),
        }

    def start_team_mode(self, team_name: str, num_workers: int) -> dict:
        """Start team mode with N workers."""
        self.state = CoordinatorState.TEAM_MODE
        self.team_name = team_name
        self.num_workers = num_workers
        self._setup_team_state()
        return {"status": "started", "team_name": team_name, "workers": num_workers}

    def _setup_team_state(self) -> None:
        """Setup team state directory."""
        if not self.team_name:
            return
        team_dir = os.path.join(".tenderclaw", "state", "team", self.team_name)
        tasks_dir = os.path.join(team_dir, "tasks")
        workers_dir = os.path.join(team_dir, "workers")
        os.makedirs(tasks_dir, exist_ok=True)
        os.makedirs(workers_dir, exist_ok=True)
        config_path = os.path.join(team_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "team_name": self.team_name,
                "num_workers": self.num_workers,
                "coordinator_id": self.id,
            }, f, indent=2)

    def get_team_status(self) -> dict:
        """Get team execution status."""
        return {
            "state": self.state.value,
            "team_name": self.team_name,
            "workers": self.num_workers,
            "tasks": {
                "pending": len([t for t in self.tasks if t.status == "pending"]),
                "in_progress": len([t for t in self.tasks if t.status == "running"]),
                "completed": len([t for t in self.tasks if t.status == "completed"]),
                "failed": len([t for t in self.tasks if t.status == "failed"]),
            }
        }

    def shutdown_team(self) -> dict:
        """Shutdown team and cleanup."""
        self.state = CoordinatorState.IDLE
        self.team_name = None
        self.num_workers = 0
        return {"status": "shutdown"}


class CoordinatorManager:
    _coordinators: dict[str, Coordinator] = {}

    @classmethod
    def create(cls, name: str) -> Coordinator:
        coordinator = Coordinator(id=str(uuid.uuid4()), name=name)
        cls._coordinators[coordinator.id] = coordinator
        return coordinator

    @classmethod
    def get(cls, coordinator_id: str) -> Coordinator | None:
        return cls._coordinators.get(coordinator_id)

    @classmethod
    def list_all(cls) -> list[Coordinator]:
        return list(cls._coordinators.values())

    @classmethod
    def delete(cls, coordinator_id: str) -> bool:
        if coordinator_id in cls._coordinators:
            del cls._coordinators[coordinator_id]
            return True
        return False