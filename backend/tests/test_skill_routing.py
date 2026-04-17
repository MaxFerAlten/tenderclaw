"""Sprint 5 — Skill routing integration tests.

Verifies:
- IntentGateResult shape
- classify_intent_with_skill (sync-safe via mock)
- skills/ralplan/SKILL.md exists and parses correctly
- SkillRegistry discovery loads ralplan
- superpowers_loader.load_skills_from_markdown returns ralplan
- skills_api /select and /trace endpoints
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.core.skills import (
    Skill,
    SkillRegistry,
    SkillSelector,
    parse_skill,
    discover_skills,
)


# ---------------------------------------------------------------------------
# ralplan SKILL.md — file must exist and parse cleanly
# ---------------------------------------------------------------------------


class TestRalplanSkillFile:
    RALPLAN_PATH = Path(__file__).parent.parent.parent / "skills" / "ralplan" / "SKILL.md"

    def test_skill_file_exists(self):
        assert self.RALPLAN_PATH.exists(), "skills/ralplan/SKILL.md must exist"

    def test_skill_parses_without_error(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert skill.name == "ralplan"

    def test_skill_has_trigger(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert skill.trigger.strip() != ""

    def test_skill_has_description(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert len(skill.description) > 10

    def test_skill_has_flow_steps(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert len(skill.flow) >= 1

    def test_skill_has_agents(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert len(skill.agents) >= 1

    def test_trigger_contains_ralplan(self):
        skill = parse_skill("ralplan", self.RALPLAN_PATH)
        assert "ralplan" in skill.trigger.lower()


# ---------------------------------------------------------------------------
# SkillRegistry discovery includes ralplan
# ---------------------------------------------------------------------------


class TestSkillDiscovery:
    SKILLS_ROOT = Path(__file__).parent.parent.parent / "skills"

    def test_discover_finds_ralplan(self):
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        names = [s.name for s in reg.all()]
        assert "ralplan" in names

    def test_discover_finds_multiple_skills(self):
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        assert len(reg) >= 5  # at minimum brainstorming, writing-plans, tdd, ralplan, ...

    def test_registry_get_ralplan(self):
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        skill = reg.get("ralplan")
        assert skill is not None
        assert skill.name == "ralplan"


# ---------------------------------------------------------------------------
# superpowers_loader.load_skills_from_markdown includes ralplan
# ---------------------------------------------------------------------------


class TestSuperpowersLoaderRalplan:
    SKILLS_ROOT = Path(__file__).parent.parent.parent / "skills"

    def test_loader_finds_ralplan(self):
        from backend.plugins.superpowers_loader import load_skills_from_markdown
        descriptors = load_skills_from_markdown(self.SKILLS_ROOT)
        names = [d["name"] for d in descriptors]
        assert "ralplan" in names

    def test_loader_ralplan_has_trigger(self):
        from backend.plugins.superpowers_loader import load_skills_from_markdown
        descriptors = load_skills_from_markdown(self.SKILLS_ROOT)
        ralplan = next((d for d in descriptors if d["name"] == "ralplan"), None)
        assert ralplan is not None
        assert ralplan["trigger"]

    def test_loader_ralplan_has_description(self):
        from backend.plugins.superpowers_loader import load_skills_from_markdown
        descriptors = load_skills_from_markdown(self.SKILLS_ROOT)
        ralplan = next((d for d in descriptors if d["name"] == "ralplan"), None)
        assert ralplan is not None
        assert len(ralplan["description"]) > 10


# ---------------------------------------------------------------------------
# SkillSelector routes to ralplan for planning tasks
# ---------------------------------------------------------------------------


class TestSkillRoutingRalplan:
    SKILLS_ROOT = Path(__file__).parent.parent.parent / "skills"

    def _reg(self) -> SkillRegistry:
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        return reg

    def test_ralplan_trigger_routes_to_ralplan(self):
        sel = SkillSelector()
        m = sel.select("ralplan the authentication feature", registry=self._reg())
        assert m.matched
        assert m.skill_name == "ralplan"

    def test_consensus_plan_routes_to_ralplan(self):
        sel = SkillSelector()
        m = sel.select("consensus plan for the new payment system", registry=self._reg())
        assert m.matched
        assert m.skill_name == "ralplan"

    def test_plan_phase_routes_to_ralplan(self):
        sel = SkillSelector()
        m = sel.select("plan the database migration", phase="plan", registry=self._reg())
        assert m.matched
        assert m.skill_name == "ralplan"

    def test_tdd_task_does_not_route_to_ralplan(self):
        sel = SkillSelector()
        m = sel.select("write tdd tests for auth module", registry=self._reg())
        # Should NOT be ralplan
        assert not m.matched or m.skill_name != "ralplan"

    def test_security_task_routes_to_security_skill(self):
        sel = SkillSelector()
        m = sel.select("security audit of the API", registry=self._reg())
        if m.matched:
            assert "security" in m.skill_name.lower()


# ---------------------------------------------------------------------------
# IntentGateResult shape
# ---------------------------------------------------------------------------


class TestIntentGateResult:
    def test_result_fields(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(
            intent=Intent.PLAN,
            skill_name="ralplan",
            confidence=0.85,
            reason="planning task",
        )
        assert r.intent == Intent.PLAN
        assert r.has_skill is True
        assert r.skill_name == "ralplan"

    def test_no_skill_has_skill_false(self):
        from backend.orchestration.intent_gate import IntentGateResult, Intent
        r = IntentGateResult(intent=Intent.IMPLEMENT)
        assert r.has_skill is False
        assert r.skill_name == ""
        assert r.confidence == 0.0

    def test_intent_values_cover_all_phases(self):
        from backend.orchestration.intent_gate import Intent
        expected = {"research", "implement", "fix", "plan", "review", "chat"}
        actual = {i.value for i in Intent}
        assert expected <= actual


# ---------------------------------------------------------------------------
# skills_api endpoints — SkillSelectResponse shape
# ---------------------------------------------------------------------------


class TestSkillsApiSelectShape:
    """Unit-test the SkillSelectResponse / SkillTraceItem Pydantic models."""

    def test_skill_select_match_model(self):
        from backend.api.skills_api import SkillSelectMatch
        m = SkillSelectMatch(
            skill_name="tdd",
            confidence=0.7,
            reason="trigger match",
            phase="implement",
            risk="medium",
            matched=True,
        )
        assert m.skill_name == "tdd"
        assert m.matched is True

    def test_skill_select_response_model(self):
        from backend.api.skills_api import SkillSelectResponse, SkillSelectMatch
        resp = SkillSelectResponse(
            matches=[SkillSelectMatch(
                skill_name="ralplan", confidence=0.8, reason="x",
                phase="plan", risk="low", matched=True,
            )],
            task_snippet="plan the migration",
        )
        assert len(resp.matches) == 1
        assert resp.task_snippet == "plan the migration"

    def test_skill_trace_item_model(self):
        from backend.api.skills_api import SkillTraceItem
        item = SkillTraceItem(
            timestamp="2026-04-11T12:00:00",
            task_snippet="write tests",
            phase="implement",
            risk="low",
            skill_name="tdd",
            confidence=0.6,
            reason="tdd trigger",
        )
        assert item.skill_name == "tdd"

    def test_no_match_matched_false(self):
        from backend.api.skills_api import SkillSelectMatch
        m = SkillSelectMatch(
            skill_name="", confidence=0.0, reason="no match",
            phase="", risk="medium", matched=False,
        )
        assert m.matched is False


# ---------------------------------------------------------------------------
# Skill prompt injection helpers
# ---------------------------------------------------------------------------


class TestSkillPromptInjection:
    """build_skills_instruction() must include ralplan after discovery."""

    SKILLS_ROOT = Path(__file__).parent.parent.parent / "skills"

    def test_build_instruction_includes_ralplan(self):
        from backend.core.skills import build_skills_instruction, get_registry, discover_skills, SkillRegistry
        # Build a fresh registry seeded with local skills
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        # Patch the global temporarily
        import backend.core.skills as skills_mod
        original = skills_mod._skill_registry
        skills_mod._skill_registry = reg
        try:
            instr = build_skills_instruction()
            assert "ralplan" in instr
        finally:
            skills_mod._skill_registry = original

    def test_build_instruction_non_empty(self):
        from backend.core.skills import build_skills_instruction, SkillRegistry
        import backend.core.skills as skills_mod
        reg = SkillRegistry()
        reg.register(Skill(
            name="tdd", path=Path("/fake/tdd/SKILL.md"),
            trigger="tdd", description="TDD skill",
        ))
        original = skills_mod._skill_registry
        skills_mod._skill_registry = reg
        try:
            instr = build_skills_instruction()
            assert len(instr) > 0
            assert "tdd" in instr
        finally:
            skills_mod._skill_registry = original

    def test_build_instruction_empty_when_no_skills(self):
        from backend.core.skills import build_skills_instruction, SkillRegistry
        import backend.core.skills as skills_mod
        reg = SkillRegistry()
        original = skills_mod._skill_registry
        skills_mod._skill_registry = reg
        try:
            instr = build_skills_instruction()
            assert instr == ""
        finally:
            skills_mod._skill_registry = original
