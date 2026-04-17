"""Sprint 4 — OMX Team Runtime tests.

Covers:
- PlanStore canonical task ID fix (reserve_canonical_id before worker bootstrap)
- WorkerPool canonical_task_id metadata + worker_health_check
- RoleRouter result shape, routing rules, overrides
- Coordinator rebalance_workers + choose_task_owner
- WisdomStore feedback_loop extraction and persistence
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# PlanStore — critical fix + canonical ID
# ---------------------------------------------------------------------------


class TestPlanStoreCanonicalId:
    def _store(self):
        from backend.orchestration.plan_store import PlanStore
        d = tempfile.mkdtemp()
        return PlanStore(storage_path=Path(d))

    def test_reserve_canonical_id_returns_string(self):
        store = self._store()
        cid = store.reserve_canonical_id("sess_1", "do something")
        assert isinstance(cid, str)
        assert cid.startswith("plan_")

    def test_reserve_canonical_id_flushes_to_disk(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            cid = store.reserve_canonical_id("sess_1", "do something")
            stub_path = Path(d) / f"{cid}.json"
            assert stub_path.exists(), "Stub must be on disk before worker bootstrap"

    def test_reserve_canonical_id_readable_before_create(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            cid = store.reserve_canonical_id("sess_x", "task x")
            # Worker looks up the plan by canonical ID — must succeed
            plan = store.get(cid)
            assert plan is not None
            assert plan.plan_id == cid

    def test_create_with_canonical_task_id_reuses_id(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            cid = store.reserve_canonical_id("sess_1", "task")
            plan = store.create("sess_1", "task", "plan content", canonical_task_id=cid)
            assert plan.plan_id == cid
            assert plan.canonical_task_id == cid

    def test_create_without_canonical_id_auto_generates(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            plan = store.create("sess_1", "some task")
            assert plan.canonical_task_id == plan.plan_id

    def test_canonical_id_unique_per_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            ids = {store.reserve_canonical_id("sess_1", f"task {i}") for i in range(10)}
            assert len(ids) == 10

    def test_reserved_id_survives_store_reload(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store1 = PlanStore(storage_path=Path(d))
            cid = store1.reserve_canonical_id("sess_r", "reload test")
            # New store instance (simulates process restart / worker bootstrap)
            store2 = PlanStore(storage_path=Path(d))
            plan = store2.get(cid)
            assert plan is not None
            assert plan.plan_id == cid

    def test_full_bootstrap_sequence(self):
        """reserve_canonical_id → bootstrap worker → create full plan."""
        with tempfile.TemporaryDirectory() as d:
            from backend.orchestration.plan_store import PlanStore
            store = PlanStore(storage_path=Path(d))
            # Step 1: reserve BEFORE bootstrap
            cid = store.reserve_canonical_id("sess_b", "implement feature X")
            # Step 2: [worker bootstraps — reads stub via get(cid)]
            stub = store.get(cid)
            assert stub is not None
            # Step 3: full plan written AFTER bootstrap
            plan = store.create("sess_b", "implement feature X", "## Plan\n1. step one", canonical_task_id=cid)
            assert plan.plan_id == cid
            assert plan.steps[0].description == "step one"


# ---------------------------------------------------------------------------
# WorkerPool — canonical_task_id + health check
# ---------------------------------------------------------------------------


class TestWorkerPoolCanonicalTaskId:
    @pytest.mark.asyncio
    async def test_submit_with_canonical_task_id(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            task = await pool.submit(
                lambda: asyncio.sleep(0),
                "test-task",
                canonical_task_id="plan_abc123",
            )
            assert task.canonical_task_id == "plan_abc123"

    @pytest.mark.asyncio
    async def test_submit_without_canonical_task_id_is_none(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            task = await pool.submit(lambda: asyncio.sleep(0), "no-plan-task")
            assert task.canonical_task_id is None

    @pytest.mark.asyncio
    async def test_to_info_includes_canonical_task_id(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            task = await pool.submit(
                lambda: asyncio.sleep(0),
                "info-task",
                canonical_task_id="plan_xyz",
            )
            info = task.to_info()
            assert info["canonical_task_id"] == "plan_xyz"


class TestWorkerPoolHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_empty_pool(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=4) as pool:
            health = pool.worker_health_check()
            assert health["healthy"] is True
            assert health["running"] == 0
            assert health["stalled_tasks"] == []

    @pytest.mark.asyncio
    async def test_health_check_unknown_task(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            health = pool.worker_health_check("nonexistent")
            assert health["healthy"] is False
            assert health["reason"] == "task_not_found"

    @pytest.mark.asyncio
    async def test_health_check_completed_task(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            task = await pool.submit_and_wait(lambda: asyncio.sleep(0), "done-task")
            health = pool.worker_health_check(task.task_id)
            assert health["status"] == "completed"
            assert health["stalled"] is False

    @pytest.mark.asyncio
    async def test_health_check_with_canonical_task_id(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=2) as pool:
            task = await pool.submit_and_wait(
                lambda: asyncio.sleep(0),
                "plan-task",
                canonical_task_id="plan_health_test",
            )
            health = pool.worker_health_check(task.task_id)
            assert health["canonical_task_id"] == "plan_health_test"

    @pytest.mark.asyncio
    async def test_health_check_aggregate_utilisation(self):
        from backend.workers.pool import WorkerPool

        async with WorkerPool(max_workers=4) as pool:
            health = pool.worker_health_check()
            assert "utilisation_pct" in health
            assert 0 <= health["utilisation_pct"] <= 100


# ---------------------------------------------------------------------------
# RoleRouter
# ---------------------------------------------------------------------------


class TestRoleRouterResult:
    def test_result_model_fields(self):
        from backend.services.role_router import RoleRouterResult, AgentTier, AgentPosture

        r = RoleRouterResult(
            agent="sisyphus",
            tier=AgentTier.STANDARD,
            posture=AgentPosture.BALANCED,
            confidence=0.9,
            reason="test",
        )
        assert r.agent == "sisyphus"
        assert r.tier == AgentTier.STANDARD
        assert 0.0 <= r.confidence <= 1.0

    def test_result_defaults(self):
        from backend.services.role_router import RoleRouterResult

        r = RoleRouterResult(agent="oracle")
        assert r.confidence == 1.0
        assert r.reason == ""
        assert r.metadata == {}


class TestRoleRouterRouting:
    def _router(self):
        from backend.services.role_router import RoleRouter
        return RoleRouter()

    def test_research_task_routes_to_oracle(self):
        r = self._router().route("research the authentication library")
        assert r.agent == "oracle"

    def test_planning_routes_to_metis(self):
        r = self._router().route("design the database schema")
        assert r.agent == "metis"

    def test_security_routes_to_sentinel(self):
        r = self._router().route("security audit of the API")
        assert r.agent == "sentinel"

    def test_debug_routes_to_fixer(self):
        r = self._router().route("fix the broken login endpoint")
        assert r.agent == "fixer"

    def test_verify_routes_to_momus(self):
        r = self._router().route("verify the migration output")
        assert r.agent == "momus"

    def test_implement_routes_to_sisyphus(self):
        r = self._router().route("implement the new payment feature")
        assert r.agent == "sisyphus"

    def test_testing_routes_to_sisyphus(self):
        r = self._router().route("write pytest fixtures for auth module")
        assert r.agent == "sisyphus"

    def test_default_fallback(self):
        r = self._router().route("do something completely generic")
        assert r.agent == "sisyphus"
        assert r.confidence == 0.5

    def test_confidence_is_float_between_0_and_1(self):
        router = self._router()
        for task in [
            "research X", "design Y", "fix Z", "implement W", "verify V",
        ]:
            r = router.route(task)
            assert 0.0 <= r.confidence <= 1.0

    def test_reason_is_non_empty(self):
        router = self._router()
        for task in ["research X", "design Y", "fix Z"]:
            r = router.route(task)
            assert len(r.reason) > 0


class TestRoleRouterOverrides:
    def _router(self):
        from backend.services.role_router import RoleRouter, AgentTier, AgentPosture
        return RoleRouter(), AgentTier, AgentPosture

    def test_force_agent_overrides_routing(self):
        router, _, _ = self._router()
        r = router.route("research something", force_agent="metis")
        assert r.agent == "metis"

    def test_force_tier_overrides(self):
        router, AgentTier, _ = self._router()
        r = router.route("research something", force_tier=AgentTier.FLAGSHIP)
        assert r.tier == AgentTier.FLAGSHIP

    def test_force_posture_overrides(self):
        router, _, AgentPosture = self._router()
        r = router.route("implement something", force_posture=AgentPosture.CONSERVATIVE)
        assert r.posture == AgentPosture.CONSERVATIVE

    def test_context_stored_in_metadata(self):
        router, _, _ = self._router()
        r = router.route("research X", context={"session_id": "abc", "pipeline": "oracle"})
        assert r.metadata["session_id"] == "abc"

    def test_explain_returns_matching_rules(self):
        router, _, _ = self._router()
        matches = router.explain("fix the broken tests")
        assert len(matches) >= 1
        assert all("agent" in m for m in matches)

    def test_route_by_keywords_alias(self):
        router, _, _ = self._router()
        r1 = router.route("security audit")
        r2 = router.route_by_keywords("security audit")
        assert r1.agent == r2.agent


# ---------------------------------------------------------------------------
# Coordinator — rebalance_workers + choose_task_owner
# ---------------------------------------------------------------------------


class TestCoordinatorChooseTaskOwner:
    def _coordinator(self):
        from backend.orchestration.coordinator import Coordinator
        return Coordinator(id="coord_1", name="test")

    def test_choose_from_single_candidate(self):
        c = self._coordinator()
        result = c.choose_task_owner("task_1", ["sisyphus"])
        assert result == "sisyphus"

    def test_prefer_agent_wins(self):
        c = self._coordinator()
        result = c.choose_task_owner("task_1", ["sisyphus", "oracle", "metis"], prefer_agent="oracle")
        assert result == "oracle"

    def test_prefer_agent_not_in_candidates_falls_back(self):
        c = self._coordinator()
        result = c.choose_task_owner("task_1", ["sisyphus", "oracle"], prefer_agent="sentinel")
        assert result in ("sisyphus", "oracle")

    def test_empty_candidates_returns_none(self):
        c = self._coordinator()
        result = c.choose_task_owner("task_1", [])
        assert result is None

    def test_least_loaded_agent_chosen(self):
        c = self._coordinator()
        # Artificially load sisyphus with 2 running tasks
        c.add_task("task A")
        c.tasks[-1].assignee = "sisyphus"
        c.tasks[-1].status = "running"
        c.add_task("task B")
        c.tasks[-1].assignee = "sisyphus"
        c.tasks[-1].status = "running"
        # oracle has 0 running tasks
        result = c.choose_task_owner("new_task", ["sisyphus", "oracle"])
        assert result == "oracle"


class TestCoordinatorRebalanceWorkers:
    def _coordinator(self):
        from backend.orchestration.coordinator import Coordinator
        c = Coordinator(id="coord_2", name="test")
        for i in range(5):
            c.add_task(f"Task {i}")
        return c

    def test_rebalance_empty_agents(self):
        c = self._coordinator()
        result = c.rebalance_workers([])
        assert result["reassigned"] == 0
        assert result["skipped"] == 5

    def test_rebalance_assigns_all_pending(self):
        c = self._coordinator()
        result = c.rebalance_workers(["sisyphus", "oracle"])
        assert result["reassigned"] == 5
        assert result["skipped"] == 0
        # All tasks now have an assignee
        assigned = [t for t in c.tasks if t.assignee is not None]
        assert len(assigned) == 5

    def test_rebalance_respects_max_per_agent(self):
        c = self._coordinator()
        result = c.rebalance_workers(["sisyphus", "oracle"], max_per_agent=2)
        # 2 agents × 2 max = 4 slots for 5 tasks
        assert result["reassigned"] == 4
        assert result["skipped"] == 1

    def test_rebalance_distributes_evenly(self):
        c = self._coordinator()
        c.rebalance_workers(["agent_a", "agent_b", "agent_c", "agent_d", "agent_e"])
        counts: dict[str, int] = {}
        for t in c.tasks:
            if t.assignee:
                counts[t.assignee] = counts.get(t.assignee, 0) + 1
        # No agent should have more than 2 (with 5 tasks / 5 agents each gets ≤1)
        assert max(counts.values()) <= 2

    def test_rebalance_returns_assignments_list(self):
        c = self._coordinator()
        result = c.rebalance_workers(["sisyphus"])
        assert len(result["assignments"]) == result["reassigned"]
        for entry in result["assignments"]:
            assert "task_id" in entry
            assert "agent" in entry

    def test_rebalance_skips_already_running_tasks(self):
        from backend.orchestration.coordinator import Coordinator
        c = Coordinator(id="coord_3", name="test")
        t1 = c.add_task("already running")
        c.assign_task(t1.id, "sisyphus")  # sets status=running
        c.add_task("pending task")
        result = c.rebalance_workers(["oracle"])
        # Only the pending task gets reassigned
        assert result["reassigned"] == 1


# ---------------------------------------------------------------------------
# WisdomStore — feedback_loop
# ---------------------------------------------------------------------------


class TestWisdomFeedbackLoop:
    def _store(self):
        from backend.memory.wisdom import WisdomStore
        d = tempfile.mkdtemp()
        return WisdomStore(storage_path=d)

    def _make_plan(self, task="implement feature X", success_score=1.0, fix_attempts=0, issues=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            task=task,
            success_score=success_score,
            fix_attempts=fix_attempts,
            issues=issues or [],
            plan_content="## Plan\n1. step one",
        )

    def test_feedback_loop_returns_wisdom_item(self):
        store = self._store()
        plan = self._make_plan()
        item = store.feedback_loop(plan, "tests passed", session_id="s1")
        assert item is not None
        assert item.id.startswith("w_")

    def test_feedback_loop_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as d:
            from backend.memory.wisdom import WisdomStore
            store = WisdomStore(storage_path=d)
            plan = self._make_plan(task="fix auth bug")
            item = store.feedback_loop(plan, "fixed", session_id="s2")
            assert item is not None
            assert (Path(d) / f"{item.id}.json").exists()

    def test_feedback_loop_skips_empty_task(self):
        store = self._store()
        item = store.feedback_loop(self._make_plan(task=""), "done")
        assert item is None

    def test_feedback_loop_skips_zero_score(self):
        store = self._store()
        item = store.feedback_loop(self._make_plan(success_score=0.0), "failed")
        assert item is None

    def test_feedback_loop_includes_fix_attempts_in_pattern(self):
        store = self._store()
        plan = self._make_plan(fix_attempts=3)
        item = store.feedback_loop(plan, "eventually passed")
        assert item is not None
        assert "3 fix attempt" in item.solution_pattern

    def test_feedback_loop_includes_issues_in_pattern(self):
        store = self._store()
        plan = self._make_plan(issues=["missing import", "type error"])
        item = store.feedback_loop(plan, "resolved")
        assert item is not None
        assert "missing import" in item.solution_pattern

    def test_feedback_loop_infers_task_type(self):
        store = self._store()
        item = store.feedback_loop(self._make_plan(task="fix the broken login"), "fixed")
        assert item is not None
        assert item.task_type == "bugfix"

    def test_feedback_loop_accepts_dict_plan(self):
        store = self._store()
        plan = {"task": "implement feature Y", "success_score": 0.8, "fix_attempts": 1, "issues": []}
        item = store.feedback_loop(plan, "done")
        assert item is not None
        assert "implement" in item.description.lower()

    def test_feedback_loop_with_code_snippet(self):
        store = self._store()
        snippet = "def foo(): return 42"
        item = store.feedback_loop(self._make_plan(), "done", code_snippet=snippet)
        assert item is not None
        assert item.code_snippet == snippet

    def test_feedback_loop_item_retrievable(self):
        store = self._store()
        plan = self._make_plan(task="implement auth module")
        store.feedback_loop(plan, "auth working")
        results = store.find_relevant("implement auth")
        assert len(results) >= 1

    def test_feedback_loop_success_score_clamped(self):
        store = self._store()
        plan = self._make_plan(success_score=5.0)  # above 1.0
        item = store.feedback_loop(plan, "very good")
        assert item is not None
        assert item.success_score <= 1.0


class TestWisdomTaskTypeInference:
    def _infer(self, task):
        from backend.memory.wisdom import _infer_task_type
        return _infer_task_type(task)

    def test_testing(self):
        assert self._infer("write pytest fixtures") == "testing"

    def test_bugfix(self):
        assert self._infer("fix the broken login") == "bugfix"

    def test_refactor(self):
        assert self._infer("refactor the auth module") == "refactor"

    def test_implementation(self):
        assert self._infer("implement the payment feature") == "implementation"

    def test_research(self):
        assert self._infer("research the best caching strategy") == "research"

    def test_devops(self):
        assert self._infer("deploy the service to production") == "devops"

    def test_security(self):
        assert self._infer("security audit of the API") == "security"

    def test_planning(self):
        assert self._infer("design the database schema") == "planning"

    def test_general_fallback(self):
        assert self._infer("do something generic") == "general"
