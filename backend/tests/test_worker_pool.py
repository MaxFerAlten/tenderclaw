"""Tests for WorkerPool — concurrency, timeout, backpressure, priority."""

from __future__ import annotations

import asyncio

import pytest

from backend.workers.pool import (
    TaskPriority,
    TaskStatus,
    WorkerPool,
    WorkerTask,
)


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(max_workers=2, default_timeout=5.0)


# --- Basic execution ---


@pytest.mark.asyncio
async def test_submit_and_wait(pool: WorkerPool):
    async with pool:
        async def work():
            return 42

        task = await pool.submit_and_wait(work, "answer")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 42
        assert task.elapsed is not None


@pytest.mark.asyncio
async def test_submit_many(pool: WorkerPool):
    results = []

    async with pool:
        async def make_fn(val):
            async def fn():
                results.append(val)
                return val
            return fn

        items = [(await make_fn(i), f"task-{i}") for i in range(5)]
        tasks = await pool.submit_many(items)
        completed = await pool.wait_all([t.task_id for t in tasks])

    assert len(completed) == 5
    assert all(t.status == TaskStatus.COMPLETED for t in completed)
    assert sorted(results) == [0, 1, 2, 3, 4]


# --- Concurrency limit ---


@pytest.mark.asyncio
async def test_max_workers_respected():
    pool = WorkerPool(max_workers=2, default_timeout=10.0)
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    async def track():
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            max_concurrent = max(max_concurrent, current)
        await asyncio.sleep(0.05)
        async with lock:
            current -= 1

    async with pool:
        tasks = []
        for i in range(6):
            t = await pool.submit(track, f"t{i}")
            tasks.append(t)
        await pool.wait_all([t.task_id for t in tasks])

    assert max_concurrent <= 2


# --- Timeout ---


@pytest.mark.asyncio
async def test_task_timeout():
    pool = WorkerPool(max_workers=2, default_timeout=0.1)

    async def slow():
        await asyncio.sleep(10)

    async with pool:
        task = await pool.submit_and_wait(slow, "slow-task")

    assert task.status == TaskStatus.TIMED_OUT
    assert "Timed out" in task.error


@pytest.mark.asyncio
async def test_per_task_timeout():
    pool = WorkerPool(max_workers=2, default_timeout=60.0)

    async def slow():
        await asyncio.sleep(10)

    async with pool:
        task = await pool.submit_and_wait(slow, "slow", timeout=0.1)

    assert task.status == TaskStatus.TIMED_OUT


# --- Error handling ---


@pytest.mark.asyncio
async def test_task_failure(pool: WorkerPool):
    async def fail():
        raise ValueError("boom")

    async with pool:
        task = await pool.submit_and_wait(fail, "failing-task")

    assert task.status == TaskStatus.FAILED
    assert "ValueError: boom" in task.error


@pytest.mark.asyncio
async def test_failure_doesnt_break_pool(pool: WorkerPool):
    async def fail():
        raise RuntimeError("oops")

    async def ok():
        return "fine"

    async with pool:
        t1 = await pool.submit(fail, "bad")
        t2 = await pool.submit(ok, "good")
        await pool.wait_all([t1.task_id, t2.task_id])

    assert t1.status == TaskStatus.FAILED
    assert t2.status == TaskStatus.COMPLETED
    assert t2.result == "fine"


# --- Cancel ---


@pytest.mark.asyncio
async def test_cancel_queued(pool: WorkerPool):
    async with pool:
        async def noop():
            pass

        task = await pool.submit(noop, "to-cancel")
        cancelled = await pool.cancel(task.task_id)
        assert cancelled is True
        assert task.status == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_completed_fails(pool: WorkerPool):
    async with pool:
        async def noop():
            pass

        task = await pool.submit_and_wait(noop, "done")
        cancelled = await pool.cancel(task.task_id)
        assert cancelled is False


@pytest.mark.asyncio
async def test_cancel_all(pool: WorkerPool):
    async with pool:
        async def noop():
            await asyncio.sleep(10)

        for i in range(5):
            await pool.submit(noop, f"t{i}")
        count = await pool.cancel_all()
        assert count >= 1


# --- Priority ---


@pytest.mark.asyncio
async def test_priority_ordering():
    """Higher priority tasks should start before lower ones."""
    # Use 1 worker to force sequential execution
    pool = WorkerPool(max_workers=1, default_timeout=5.0)
    execution_order: list[str] = []

    async def make_fn(name):
        async def fn():
            execution_order.append(name)
        return fn

    async with pool:
        # Submit low first, then high — high should run before low
        # But the first task submitted may already be running
        # So we submit a blocker first
        blocker_done = asyncio.Event()

        async def blocker():
            await blocker_done.wait()

        await pool.submit(blocker, "blocker")
        await asyncio.sleep(0.05)  # let blocker start

        await pool.submit(await make_fn("low"), "low", priority=TaskPriority.LOW)
        await pool.submit(await make_fn("high"), "high", priority=TaskPriority.HIGH)
        await pool.submit(await make_fn("critical"), "critical", priority=TaskPriority.CRITICAL)

        blocker_done.set()
        await pool.wait_all()

    # After blocker finishes, priority order should be: critical, high, low
    assert execution_order == ["critical", "high", "low"]


# --- Progress & Stats ---


@pytest.mark.asyncio
async def test_get_progress(pool: WorkerPool):
    async with pool:
        async def ok():
            return 1

        async def fail():
            raise ValueError("x")

        t1 = await pool.submit(ok, "ok")
        t2 = await pool.submit(fail, "fail")
        await pool.wait_all([t1.task_id, t2.task_id])

        progress = pool.get_progress()
        assert progress["total"] == 2
        assert progress["completed"] == 1
        assert progress["failed"] == 1
        assert progress["percent"] == 100


@pytest.mark.asyncio
async def test_get_stats(pool: WorkerPool):
    async with pool:
        async def ok():
            return 1

        tasks = []
        for i in range(3):
            t = await pool.submit(ok, f"t{i}")
            tasks.append(t)
        await pool.wait_all([t.task_id for t in tasks])

    stats = pool.get_stats()
    assert stats["total_submitted"] == 3
    assert stats["total_completed"] == 3
    assert stats["max_workers"] == 2
    assert stats["peak_concurrency"] <= 2


# --- Query ---


@pytest.mark.asyncio
async def test_get_task(pool: WorkerPool):
    async with pool:
        async def ok():
            pass

        task = await pool.submit(ok, "findme")
        found = pool.get_task(task.task_id)
        assert found is not None
        assert found.name == "findme"


@pytest.mark.asyncio
async def test_list_tasks_by_status(pool: WorkerPool):
    async with pool:
        async def ok():
            pass

        async def fail():
            raise ValueError("x")

        t1 = await pool.submit(ok, "ok")
        t2 = await pool.submit(fail, "fail")
        await pool.wait_all([t1.task_id, t2.task_id])

        completed = pool.list_tasks(TaskStatus.COMPLETED)
        failed = pool.list_tasks(TaskStatus.FAILED)
        assert len(completed) == 1
        assert len(failed) == 1


# --- Task info ---


def test_task_to_info():
    async def noop():
        pass

    task = WorkerTask(
        task_id="wt_123",
        name="test-task",
        fn=noop,
        agent_name="sisyphus",
    )
    info = task.to_info()
    assert info["task_id"] == "wt_123"
    assert info["name"] == "test-task"
    assert info["agent"] == "sisyphus"
    assert info["status"] == "queued"


# --- Hooks ---


@pytest.mark.asyncio
async def test_task_hooks(pool: WorkerPool):
    events: list[tuple[str, str]] = []

    async def hook(task: WorkerTask):
        events.append((task.name, task.status.value))

    pool.on_task_event(hook)

    async with pool:
        async def ok():
            return 1

        task = await pool.submit_and_wait(ok, "hooked")

    # Should fire on start and complete
    assert ("hooked", "running") in events
    assert ("hooked", "completed") in events


# --- Context manager ---


@pytest.mark.asyncio
async def test_context_manager():
    async with WorkerPool(max_workers=1) as pool:
        async def ok():
            return "yes"

        task = await pool.submit_and_wait(ok, "ctx")
        assert task.result == "yes"


# --- Metadata ---


@pytest.mark.asyncio
async def test_agent_name_and_metadata(pool: WorkerPool):
    async with pool:
        async def ok():
            return 1

        task = await pool.submit(
            ok, "meta-task",
            agent_name="hephaestus",
            metadata={"step": 3},
        )
        await pool.wait_for(task.task_id)

    assert task.agent_name == "hephaestus"
    assert task.metadata["step"] == 3
