"""Coordinator mode for managing multiple agent sessions."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
import asyncio
import uuid

logger = logging.getLogger("tenderclaw.orchestration.coordinator")


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

    def choose_task_owner(
        self,
        task_id: str,
        candidates: list[str],
        *,
        prefer_agent: str | None = None,
    ) -> str | None:
        """Select the best candidate agent to own a task.

        Selection criteria (in priority order):
        1. ``prefer_agent`` if it is in *candidates*.
        2. The candidate that currently owns the fewest running tasks.
        3. The first candidate in the list (stable fallback).

        Returns the chosen agent name, or ``None`` if *candidates* is empty.
        """
        if not candidates:
            return None

        if prefer_agent and prefer_agent in candidates:
            logger.info("choose_task_owner: preferred agent %s chosen for task %s", prefer_agent, task_id)
            return prefer_agent

        # Count how many running tasks each candidate already owns
        load: dict[str, int] = {c: 0 for c in candidates}
        for task in self.tasks:
            if task.status == "running" and task.assignee in load:
                load[task.assignee] += 1

        chosen = min(candidates, key=lambda c: load[c])
        logger.info(
            "choose_task_owner: agent %s chosen for task %s (load=%s)",
            chosen, task_id, load,
        )
        return chosen

    def rebalance_workers(
        self,
        available_agents: list[str],
        *,
        max_per_agent: int = 3,
    ) -> dict[str, Any]:
        """Reassign pending tasks to underloaded agents.

        Iterates over all ``pending`` tasks and assigns each to the agent in
        *available_agents* that currently has the fewest running tasks, as long
        as that agent hasn't exceeded *max_per_agent* running tasks.

        Returns a summary dict with ``reassigned`` (count), ``skipped`` (count),
        and ``assignments`` (list of task_id → agent mappings).
        """
        if not available_agents:
            pending_count = sum(1 for t in self.tasks if t.status == "pending")
            return {"reassigned": 0, "skipped": pending_count, "assignments": []}

        # Current load per available agent
        load: dict[str, int] = {a: 0 for a in available_agents}
        for task in self.tasks:
            if task.status == "running" and task.assignee in load:
                load[task.assignee] += 1

        pending = [t for t in self.tasks if t.status == "pending"]
        reassigned = 0
        skipped = 0
        assignments: list[dict[str, str]] = []

        for task in pending:
            # Find least-loaded agent below cap
            eligible = [a for a in available_agents if load[a] < max_per_agent]
            if not eligible:
                skipped += 1
                continue
            target = min(eligible, key=lambda a: load[a])
            task.assignee = target
            task.status = "running"
            load[target] += 1
            reassigned += 1
            assignments.append({"task_id": task.id, "agent": target})
            logger.info("rebalance_workers: task %s → %s", task.id, target)

        result: dict[str, Any] = {
            "reassigned": reassigned,
            "skipped": skipped,
            "assignments": assignments,
        }
        logger.info(
            "rebalance_workers: %d reassigned, %d skipped (max_per_agent=%d)",
            reassigned, skipped, max_per_agent,
        )
        return result


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