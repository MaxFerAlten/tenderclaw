"""Tests for PlanStore — plan persistence, lifecycle, and retrieval."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.orchestration.plan_store import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStore,
    _parse_steps,
    _suggest_tags,
)


@pytest.fixture
def tmp_store(tmp_path: Path) -> PlanStore:
    """Create a PlanStore backed by a temp directory."""
    return PlanStore(storage_path=tmp_path)


# --- Creation ---


def test_create_plan(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Add login page")
    assert plan.plan_id.startswith("plan_")
    assert plan.session_id == "sess_1"
    assert plan.task == "Add login page"
    assert plan.status == PlanStatus.DRAFT


def test_create_plan_with_content(tmp_store: PlanStore) -> None:
    content = "1. Create component\n2. Add routes\n3. Write tests"
    plan = tmp_store.create("sess_1", "Add login page", plan_content=content)
    assert len(plan.steps) == 3
    assert plan.steps[0].description == "Create component"
    assert plan.steps[2].description == "Write tests"


def test_create_plan_with_pipeline(tmp_store: PlanStore) -> None:
    plan = tmp_store.create(
        "sess_1",
        "Refactor API",
        pipeline_id="pipe_abc",
        research_summary="Found 3 endpoints",
    )
    assert plan.pipeline_id == "pipe_abc"
    assert plan.research_summary == "Found 3 endpoints"


# --- Persistence ---


def test_persist_and_reload(tmp_path: Path) -> None:
    store1 = PlanStore(storage_path=tmp_path)
    plan = store1.create("sess_1", "Build feature X", "1. Step A\n2. Step B")
    plan_id = plan.plan_id

    # New store instance loads from disk
    store2 = PlanStore(storage_path=tmp_path)
    loaded = store2.get(plan_id)
    assert loaded is not None
    assert loaded.task == "Build feature X"
    assert len(loaded.steps) == 2


def test_disk_file_written(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Test disk write")
    path = tmp_store._storage / f"{plan.plan_id}.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["task"] == "Test disk write"


# --- Get ---


def test_get_existing(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Task A")
    result = tmp_store.get(plan.plan_id)
    assert result is not None
    assert result.plan_id == plan.plan_id


def test_get_missing(tmp_store: PlanStore) -> None:
    assert tmp_store.get("nonexistent") is None


# --- List ---


def test_list_for_session(tmp_store: PlanStore) -> None:
    tmp_store.create("sess_1", "Task A")
    tmp_store.create("sess_1", "Task B")
    tmp_store.create("sess_2", "Task C")

    plans = tmp_store.list_for_session("sess_1")
    assert len(plans) == 2
    assert all(p.session_id == "sess_1" for p in plans)


def test_list_recent(tmp_store: PlanStore) -> None:
    for i in range(5):
        tmp_store.create("sess_1", f"Task {i}")
    plans = tmp_store.list_recent(limit=3)
    assert len(plans) == 3


# --- Delete ---


def test_delete_plan(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "To delete")
    assert tmp_store.delete(plan.plan_id) is True
    assert tmp_store.get(plan.plan_id) is None


def test_delete_nonexistent(tmp_store: PlanStore) -> None:
    assert tmp_store.delete("nope") is False


# --- Lifecycle ---


def test_update_status(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Lifecycle test")
    tmp_store.update_status(plan.plan_id, PlanStatus.ACTIVE)
    assert tmp_store.get(plan.plan_id).status == PlanStatus.ACTIVE

    tmp_store.update_status(plan.plan_id, PlanStatus.EXECUTING)
    assert tmp_store.get(plan.plan_id).status == PlanStatus.EXECUTING


def test_update_status_with_issues(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Issue test")
    tmp_store.update_status(
        plan.plan_id,
        PlanStatus.FAILED,
        issues=["Bug in auth", "Missing test"],
    )
    updated = tmp_store.get(plan.plan_id)
    assert updated.status == PlanStatus.FAILED
    assert len(updated.issues) == 2
    assert updated.completed_at is not None


def test_complete_sets_score(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Complete test", "1. A\n2. B")
    tmp_store.complete(plan.plan_id, success_score=0.9)
    updated = tmp_store.get(plan.plan_id)
    assert updated.status == PlanStatus.COMPLETED
    assert updated.success_score == 0.9
    assert updated.completed_at is not None


def test_complete_skips_pending_steps(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Steps test", "1. A\n2. B\n3. C")
    tmp_store.mark_step(plan.plan_id, 1, "done")
    tmp_store.complete(plan.plan_id)
    updated = tmp_store.get(plan.plan_id)
    assert updated.steps[0].status == "done"
    assert updated.steps[1].status == "skipped"
    assert updated.steps[2].status == "skipped"


def test_mark_step(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Step test", "1. First\n2. Second")
    tmp_store.mark_step(plan.plan_id, 1, "in_progress")
    updated = tmp_store.get(plan.plan_id)
    assert updated.steps[0].status == "in_progress"
    assert updated.steps[1].status == "pending"


def test_record_fix_attempt(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("sess_1", "Fix test")
    tmp_store.record_fix_attempt(plan.plan_id, ["issue 1"])
    tmp_store.record_fix_attempt(plan.plan_id, ["issue 2"])
    updated = tmp_store.get(plan.plan_id)
    assert updated.fix_attempts == 2
    assert len(updated.issues) == 2


# --- Retrieval ---


def test_find_similar(tmp_store: PlanStore) -> None:
    p1 = tmp_store.create("s1", "Add user login page with OAuth")
    tmp_store.complete(p1.plan_id, success_score=0.8)
    p2 = tmp_store.create("s1", "Fix database migration script")
    tmp_store.complete(p2.plan_id, success_score=1.0)

    results = tmp_store.find_similar("Add login form")
    assert len(results) >= 1
    assert results[0].plan_id == p1.plan_id


def test_find_similar_excludes_active(tmp_store: PlanStore) -> None:
    p = tmp_store.create("s1", "Add login page")
    # Plan is still DRAFT, should not appear
    results = tmp_store.find_similar("Add login form")
    assert len(results) == 0


def test_format_similar_for_prompt(tmp_store: PlanStore) -> None:
    p = tmp_store.create("s1", "Build API endpoint")
    tmp_store.complete(p.plan_id, success_score=1.0)
    ctx = tmp_store.format_similar_for_prompt("Create API endpoint")
    assert "Past Plans" in ctx
    assert "Build API endpoint" in ctx


def test_format_similar_empty(tmp_store: PlanStore) -> None:
    assert tmp_store.format_similar_for_prompt("Something unrelated") == ""


# --- Prompt context ---


def test_to_prompt_context(tmp_store: PlanStore) -> None:
    plan = tmp_store.create("s1", "Build feature", "1. Design\n2. Implement\n3. Test")
    tmp_store.mark_step(plan.plan_id, 1, "done")
    updated = tmp_store.get(plan.plan_id)
    ctx = updated.to_prompt_context()
    assert "[x] 1. Design" in ctx
    assert "[ ] 2. Implement" in ctx


# --- Stats ---


def test_get_stats(tmp_store: PlanStore) -> None:
    p1 = tmp_store.create("s1", "Task 1", "1. A\n2. B")
    tmp_store.complete(p1.plan_id, success_score=0.8)
    p2 = tmp_store.create("s1", "Task 2", "1. X")
    tmp_store.complete(p2.plan_id, success_score=1.0)

    stats = tmp_store.get_stats()
    assert stats["total"] == 2
    assert stats["by_status"]["completed"] == 2
    assert stats["avg_success_score"] == pytest.approx(0.9)


# --- Helpers ---


def test_parse_steps_numbered() -> None:
    content = "1. First step\n2. Second step\n3. Third step"
    steps = _parse_steps(content)
    assert len(steps) == 3
    assert steps[0].index == 1
    assert steps[2].description == "Third step"


def test_parse_steps_with_paren() -> None:
    content = "1) Do A\n2) Do B"
    steps = _parse_steps(content)
    assert len(steps) == 2


def test_parse_steps_empty() -> None:
    assert _parse_steps("No numbered steps here") == []


def test_suggest_tags() -> None:
    tags = _suggest_tags("Build a FastAPI endpoint with pytest tests")
    assert "python" in tags
    assert "api" in tags
    assert "testing" in tags


def test_suggest_tags_empty() -> None:
    assert _suggest_tags("something generic") == []
