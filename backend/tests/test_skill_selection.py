"""Sprint 5 — SkillSelector unit tests.

Verifies SkillMatch shape, scoring, confidence threshold, phase affinity,
risk adjustments, trace, and fallback behaviour.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.core.skills import (
    Skill,
    SkillMatch,
    SkillRegistry,
    SkillSelector,
    SkillTraceEntry,
    skill_selector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(name: str, trigger: str = "", description: str = "", agents: list | None = None) -> Skill:
    return Skill(
        name=name,
        path=Path(f"/fake/{name}/SKILL.md"),
        trigger=trigger or name,
        description=description or f"{name} skill",
        agents=agents or [],
    )


def _registry(*skills: Skill) -> SkillRegistry:
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    return reg


# ---------------------------------------------------------------------------
# SkillMatch model
# ---------------------------------------------------------------------------


class TestSkillMatch:
    def test_matched_true_when_skill_and_confidence(self):
        skill = _make_skill("tdd")
        m = SkillMatch(skill=skill, skill_name="tdd", confidence=0.8, reason="test")
        assert m.matched is True

    def test_matched_false_when_no_skill(self):
        m = SkillMatch(skill=None, skill_name="", confidence=0.0, reason="no match")
        assert m.matched is False

    def test_matched_false_when_confidence_zero(self):
        skill = _make_skill("tdd")
        m = SkillMatch(skill=skill, skill_name="tdd", confidence=0.0, reason="zero")
        assert m.matched is False

    def test_fields_accessible(self):
        skill = _make_skill("ralplan")
        m = SkillMatch(skill=skill, skill_name="ralplan", confidence=0.7, reason="planning task", phase="plan", risk="medium")
        assert m.skill_name == "ralplan"
        assert m.phase == "plan"
        assert m.risk == "medium"


# ---------------------------------------------------------------------------
# SkillSelector.select — basic routing
# ---------------------------------------------------------------------------


class TestSkillSelectorSelect:
    def _sel(self, *skills: Skill) -> SkillSelector:
        sel = SkillSelector()
        self._reg = _registry(*skills)
        return sel

    def test_trigger_exact_match(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        m = sel.select("write tdd tests for auth", registry=reg)
        assert m.matched
        assert m.skill_name == "tdd"

    def test_keyword_overlap_match(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("security-review", trigger="security-review", description="security audit"))
        m = sel.select("I need a security audit of the API", registry=reg)
        assert m.matched
        assert m.skill_name == "security-review"

    def test_no_match_returns_empty(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("ralplan", trigger="ralplan"))
        m = sel.select("completely unrelated xyz task abc", registry=reg)
        assert not m.matched
        assert m.skill_name == ""
        assert m.confidence == 0.0

    def test_confidence_between_0_and_1(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        m = sel.select("tdd tests please", registry=reg)
        assert 0.0 <= m.confidence <= 1.0

    def test_reason_is_non_empty_on_match(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        m = sel.select("tdd tests please", registry=reg)
        assert m.matched
        assert len(m.reason) > 0

    def test_empty_registry_returns_no_match(self):
        sel = SkillSelector()
        reg = _registry()
        m = sel.select("do something", registry=reg)
        assert not m.matched

    def test_phase_stored_in_match(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("ralplan", trigger="ralplan"))
        m = sel.select("ralplan consensus", phase="plan", registry=reg)
        assert m.phase == "plan"

    def test_risk_stored_in_match(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("ralplan", trigger="ralplan"))
        m = sel.select("ralplan consensus", risk="high", registry=reg)
        assert m.risk == "high"

    def test_best_skill_wins_when_multiple_registered(self):
        sel = SkillSelector()
        skills = [
            _make_skill("ralplan", trigger="ralplan", description="consensus planning"),
            _make_skill("tdd", trigger="tdd", description="test driven development"),
        ]
        reg = _registry(*skills)
        m = sel.select("ralplan consensus planning", registry=reg)
        assert m.skill_name == "ralplan"


# ---------------------------------------------------------------------------
# Phase affinity
# ---------------------------------------------------------------------------


class TestSkillSelectorPhaseAffinity:
    def test_plan_phase_prefers_ralplan(self):
        sel = SkillSelector()
        skills = [
            _make_skill("ralplan"),
            _make_skill("tdd"),
            _make_skill("deepsearch"),
        ]
        reg = _registry(*skills)
        m = sel.select("plan the new feature", phase="plan", registry=reg)
        # ralplan should score higher due to phase affinity
        assert m.skill_name == "ralplan"

    def test_research_phase_prefers_deepsearch(self):
        sel = SkillSelector()
        skills = [
            _make_skill("deepsearch", trigger="deepsearch", description="deep search research"),
            _make_skill("tdd"),
        ]
        reg = _registry(*skills)
        m = sel.select("research the codebase", phase="research", registry=reg)
        assert m.skill_name == "deepsearch"

    def test_review_phase_prefers_code_review(self):
        sel = SkillSelector()
        skills = [
            _make_skill("code-review", trigger="code-review", description="code review audit"),
            _make_skill("autopilot"),
        ]
        reg = _registry(*skills)
        m = sel.select("review the pull request", phase="review", registry=reg)
        assert m.skill_name == "code-review"


# ---------------------------------------------------------------------------
# Risk adjustments
# ---------------------------------------------------------------------------


class TestSkillSelectorRisk:
    def test_high_risk_boosts_security_skill(self):
        sel = SkillSelector()
        skills = [
            _make_skill("security", trigger="security", description="security review"),
            _make_skill("autopilot", trigger="autopilot", description="autopilot execution"),
        ]
        reg = _registry(*skills)
        m = sel.select("check the security vulnerabilities", risk="high", registry=reg)
        assert m.skill_name == "security"

    def test_high_risk_penalises_autopilot(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("autopilot", trigger="autopilot", description="autopilot execution"))
        # autopilot gets a penalty for high risk
        m_low = sel.select("autopilot task", risk="low", registry=reg)
        m_high = sel.select("autopilot task", risk="high", registry=reg)
        # confidence should be lower for high risk
        assert m_high.confidence <= m_low.confidence


# ---------------------------------------------------------------------------
# select_many
# ---------------------------------------------------------------------------


class TestSkillSelectorSelectMany:
    def test_returns_list(self):
        sel = SkillSelector()
        skills = [
            _make_skill("tdd", trigger="tdd"),
            _make_skill("ralplan", trigger="ralplan"),
            _make_skill("deepsearch", trigger="deepsearch"),
        ]
        reg = _registry(*skills)
        results = sel.select_many("tdd ralplan tests", limit=3, registry=reg)
        assert isinstance(results, list)

    def test_all_results_above_threshold(self):
        sel = SkillSelector()
        skills = [_make_skill("tdd", trigger="tdd"), _make_skill("ralplan", trigger="ralplan")]
        reg = _registry(*skills)
        results = sel.select_many("tdd ralplan planning", limit=5, registry=reg)
        for m in results:
            assert m.confidence >= sel.CONFIDENCE_THRESHOLD

    def test_respects_limit(self):
        sel = SkillSelector()
        skills = [_make_skill(f"skill_{i}", trigger=f"skill_{i}") for i in range(10)]
        reg = _registry(*skills)
        results = sel.select_many("skill_0 skill_1 skill_2", limit=2, registry=reg)
        assert len(results) <= 2

    def test_empty_when_no_registry(self):
        sel = SkillSelector()
        reg = _registry()
        results = sel.select_many("something", registry=reg)
        assert results == []


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class TestSkillSelectorTrace:
    def test_trace_records_selection(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        sel.select("tdd tests", registry=reg)
        trace = sel.get_trace()
        assert len(trace) >= 1
        assert isinstance(trace[0], SkillTraceEntry)

    def test_trace_newest_first(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"), _make_skill("ralplan", trigger="ralplan"))
        sel.select("tdd tests", registry=reg)
        sel.select("ralplan plan", registry=reg)
        trace = sel.get_trace()
        assert trace[0].task_snippet.startswith("ralplan")

    def test_trace_records_no_match(self):
        sel = SkillSelector()
        reg = _registry()
        sel.select("no match task", registry=reg)
        trace = sel.get_trace()
        assert len(trace) >= 1
        assert trace[0].skill_name == ""

    def test_trace_limit(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        for i in range(10):
            sel.select(f"tdd task {i}", registry=reg)
        trace = sel.get_trace(limit=3)
        assert len(trace) <= 3

    def test_clear_trace(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        sel.select("tdd tests", registry=reg)
        sel.clear_trace()
        assert sel.get_trace() == []

    def test_trace_has_required_fields(self):
        sel = SkillSelector()
        reg = _registry(_make_skill("tdd", trigger="tdd"))
        sel.select("tdd tests for auth", phase="implement", risk="low", registry=reg)
        entry = sel.get_trace()[0]
        assert entry.phase == "implement"
        assert entry.risk == "low"
        assert entry.timestamp is not None
        assert len(entry.task_snippet) > 0


# ---------------------------------------------------------------------------
# Global singleton smoke-test
# ---------------------------------------------------------------------------


class TestSkillSelectorSingleton:
    def test_singleton_is_skill_selector(self):
        assert isinstance(skill_selector, SkillSelector)

    def test_singleton_select_returns_match(self):
        # Just verify it doesn't raise even if no skills loaded in test env
        m = skill_selector.select("write some tests")
        assert isinstance(m, SkillMatch)
