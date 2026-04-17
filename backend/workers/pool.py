"""WorkerPool — async pool for parallel agent task execution.

Provides bounded concurrency with backpressure, per-task timeout,
priority queue, and progress tracking. Used by the Coordinator and
Sisyphus for parallel agent delegation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Awaitable, Callable

logger = logging.getLogger("tenderclaw.workers.pool")


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


TaskFn = Callable[[], Awaitable[Any]]


@dataclass
class WorkerTask:
    """A unit of work submitted to the pool."""

    task_id: str
    name: str
    fn: TaskFn
    status: TaskStatus = TaskStatus.QUEUED
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: float | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None
    agent_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Canonical plan ID from PlanStore — set BEFORE worker bootstrap so the
    # worker can always resolve its plan (OMX v0.8.9 fix).
    canonical_task_id: str | None = None

    @property
    def elapsed(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_info(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.value,
            "agent": self.agent_name,
            "elapsed": self.elapsed,
            "error": self.error,
            "canonical_task_id": self.canonical_task_id,
        }


@dataclass
class WorkerPoolStats:
    total_submitted: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    total_timed_out: int = 0
    peak_concurrency: int = 0


class WorkerPool:
    """Async worker pool with bounded concurrency, backpressure, and priority.

    Args:
        max_workers: Maximum concurrent tasks.
        max_queue_size: Maximum queued tasks (0 = unlimited). When full,
            submit() blocks until a slot opens (backpressure).
        default_timeout: Default per-task timeout in seconds (None = no limit).
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 0,
        default_timeout: float | None = 120.0,
    ) -> None:
        self._max_workers = max_workers
        self._default_timeout = default_timeout
        self._semaphore = asyncio.Semaphore(max_workers)
        self._queue: asyncio.PriorityQueue[tuple[int, int, WorkerTask]] = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._seq = 0  # tiebreaker for equal priority
        self._tasks: dict[str, WorkerTask] = {}
        self._running: set[str] = set()
        self._consumer_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()
        self._stats = WorkerPoolStats()
        self._hooks: list[Callable[[WorkerTask], Awaitable[None]]] = []

    # --- Lifecycle ---

    def start(self) -> None:
        """Start the pool consumer loop."""
        if self._consumer_task is not None:
            return
        self._shutdown.clear()
        self._consumer_task = asyncio.ensure_future(self._consume_loop())
        logger.info("WorkerPool started (max_workers=%d)", self._max_workers)

    async def shutdown(self, cancel_running: bool = False) -> None:
        """Shutdown the pool, optionally cancelling running tasks."""
        self._shutdown.set()
        if cancel_running:
            await self.cancel_all()
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        logger.info("WorkerPool shut down")

    # --- Submit ---

    async def submit(
        self,
        fn: TaskFn,
        name: str = "",
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float | None = None,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        canonical_task_id: str | None = None,
    ) -> WorkerTask:
        """Submit a task to the pool. Blocks if queue is full (backpressure).

        Pass ``canonical_task_id`` when submitting a task whose plan was
        pre-reserved via ``PlanStore.reserve_canonical_id()`` so the worker
        carries the stable plan reference from the moment it enters the queue.
        """
        task = WorkerTask(
            task_id=f"wt_{uuid.uuid4().hex[:10]}",
            name=name or f"task-{self._stats.total_submitted}",
            fn=fn,
            priority=priority,
            timeout=timeout if timeout is not None else self._default_timeout,
            agent_name=agent_name,
            metadata=metadata or {},
            canonical_task_id=canonical_task_id,
        )
        self._tasks[task.task_id] = task
        self._stats.total_submitted += 1

        # Priority queue uses (negative_priority, seq) for ordering
        # Higher priority = lower sort key = processed first; seq breaks ties
        self._seq += 1
        await self._queue.put((-priority, self._seq, task))
        logger.debug("Task submitted: %s (priority=%s)", task.name, priority.name)
        return task

    async def submit_many(
        self,
        items: list[tuple[TaskFn, str]],
        **kwargs: Any,
    ) -> list[WorkerTask]:
        """Submit multiple tasks and return all task handles."""
        tasks = []
        for fn, name in items:
            t = await self.submit(fn, name, **kwargs)
            tasks.append(t)
        return tasks

    async def submit_and_wait(
        self,
        fn: TaskFn,
        name: str = "",
        **kwargs: Any,
    ) -> WorkerTask:
        """Submit a task and wait for it to complete."""
        task = await self.submit(fn, name, **kwargs)
        await self.wait_for(task.task_id)
        return task

    # --- Execution ---

    async def _consume_loop(self) -> None:
        """Main consumer loop: pull tasks and execute with concurrency limit."""
        while not self._shutdown.is_set():
            try:
                _, _, task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                continue

            if task.status == TaskStatus.CANCELLED:
                self._queue.task_done()
                continue

            asyncio.ensure_future(self._run_task(task))
            self._queue.task_done()

    async def _run_task(self, task: WorkerTask) -> None:
        """Execute a single task with semaphore, timeout, and error handling."""
        async with self._semaphore:
            if task.status == TaskStatus.CANCELLED:
                return

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running.add(task.task_id)
            self._stats.peak_concurrency = max(
                self._stats.peak_concurrency, len(self._running)
            )

            logger.info("Task started: %s", task.name)
            await self._fire_hooks(task)

            try:
                if task.timeout and task.timeout > 0:
                    task.result = await asyncio.wait_for(task.fn(), timeout=task.timeout)
                else:
                    task.result = await task.fn()

                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                self._stats.total_completed += 1
                logger.info("Task completed: %s (%.2fs)", task.name, task.elapsed or 0)

            except asyncio.TimeoutError:
                task.status = TaskStatus.TIMED_OUT
                task.error = f"Timed out after {task.timeout}s"
                task.completed_at = datetime.now()
                self._stats.total_timed_out += 1
                logger.warning("Task timed out: %s", task.name)

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                self._stats.total_cancelled += 1

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.error = f"{type(exc).__name__}: {exc}"
                task.completed_at = datetime.now()
                self._stats.total_failed += 1
                logger.error("Task failed: %s — %s", task.name, task.error)

            finally:
                self._running.discard(task.task_id)
                await self._fire_hooks(task)

    # --- Control ---

    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or running task."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        self._stats.total_cancelled += 1
        logger.info("Task cancelled: %s", task.name)
        return True

    async def cancel_all(self) -> int:
        """Cancel all queued and running tasks. Returns count cancelled."""
        count = 0
        for task in list(self._tasks.values()):
            if task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                count += 1
        self._stats.total_cancelled += count
        return count

    # --- Query ---

    def get_task(self, task_id: str) -> WorkerTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[WorkerTask]:
        if status is not None:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    async def wait_for(self, task_id: str, poll_interval: float = 0.05) -> WorkerTask | None:
        """Wait for a specific task to finish."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        while task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            await asyncio.sleep(poll_interval)
        return task

    async def wait_all(self, task_ids: list[str] | None = None) -> list[WorkerTask]:
        """Wait for all (or specific) tasks to finish."""
        targets = task_ids or list(self._tasks.keys())
        results = await asyncio.gather(
            *(self.wait_for(tid) for tid in targets)
        )
        return [r for r in results if r is not None]

    def get_progress(self) -> dict[str, Any]:
        """Get pool progress summary."""
        total = len(self._tasks)
        done = sum(
            1 for t in self._tasks.values()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED)
        )
        return {
            "total": total,
            "completed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            "running": len(self._running),
            "queued": sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED),
            "percent": int(done / total * 100) if total else 0,
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_submitted": self._stats.total_submitted,
            "total_completed": self._stats.total_completed,
            "total_failed": self._stats.total_failed,
            "total_cancelled": self._stats.total_cancelled,
            "total_timed_out": self._stats.total_timed_out,
            "peak_concurrency": self._stats.peak_concurrency,
            "current_running": len(self._running),
            "max_workers": self._max_workers,
        }

    def worker_health_check(self, task_id: str | None = None) -> dict[str, Any]:
        """Return health metrics for the pool or a specific task.

        When ``task_id`` is given, returns per-task health including whether it
        is stalled (running longer than its timeout without completing).
        When omitted, returns aggregate pool health.
        """
        if task_id is not None:
            task = self._tasks.get(task_id)
            if task is None:
                return {"healthy": False, "reason": "task_not_found", "task_id": task_id}
            stalled = False
            stall_reason = None
            if task.status == TaskStatus.RUNNING and task.timeout and task.timeout > 0:
                elapsed = task.elapsed or 0
                if elapsed > task.timeout * 1.1:  # 10 % grace window
                    stalled = True
                    stall_reason = f"running {elapsed:.1f}s vs timeout {task.timeout}s"
            return {
                "healthy": not stalled,
                "task_id": task_id,
                "status": task.status.value,
                "elapsed": task.elapsed,
                "stalled": stalled,
                "stall_reason": stall_reason,
                "canonical_task_id": task.canonical_task_id,
                "agent": task.agent_name,
            }

        # Aggregate pool health
        running_count = len(self._running)
        stalled_tasks = []
        for t in self._tasks.values():
            if t.status == TaskStatus.RUNNING and t.timeout and t.timeout > 0:
                elapsed = t.elapsed or 0
                if elapsed > t.timeout * 1.1:
                    stalled_tasks.append(t.task_id)

        return {
            "healthy": len(stalled_tasks) == 0,
            "running": running_count,
            "max_workers": self._max_workers,
            "utilisation_pct": int(running_count / self._max_workers * 100) if self._max_workers else 0,
            "stalled_tasks": stalled_tasks,
            "queued": sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED),
            "total_submitted": self._stats.total_submitted,
            "total_completed": self._stats.total_completed,
            "total_failed": self._stats.total_failed,
        }

    # --- Hooks ---

    def on_task_event(self, hook: Callable[[WorkerTask], Awaitable[None]]) -> None:
        """Register a hook called on task start/complete/fail."""
        self._hooks.append(hook)

    async def _fire_hooks(self, task: WorkerTask) -> None:
        for hook in self._hooks:
            try:
                await hook(task)
            except Exception as exc:
                logger.warning("Worker hook error: %s", exc)

    # --- Context manager ---

    async def __aenter__(self) -> WorkerPool:
        self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.shutdown()


# Module-level instance
worker_pool = WorkerPool()
