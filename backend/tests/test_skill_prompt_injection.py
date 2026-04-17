"""Sprint 5 — Skill prompt injection tests.

Verifies that:
- build_skills_instruction() produces well-formed prompts
- match_trigger() returns the right skills
- SkillSelector.select() traces are observable
- Skills-API /select endpoint behaviour (unit-level, no HTTP)
- Fallback: missing skill doesn't break the pipeline
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.skills import (
    Skill,
    SkillMatch,
    SkillRegistry,
    SkillSelector,
    build_skills_instruction,
    match_trigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill(name: str, trigger: str = "", description: str = "") -> Skill:
    return Skill(
        name=name,
        path=Path(f"/fake/{name}/SKILL.md"),
        trigger=trigger or name,
        description=description or f"{name} skill",
    )


def _patched_registry(*skills: Skill):
    """Context manager that temporarily replaces the global skill registry."""
    import backend.core.skills as m
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    original = m._skill_registry
    m._skill_registry = reg
    return original, reg


# ---------------------------------------------------------------------------
# build_skills_instruction
# ---------------------------------------------------------------------------


class TestBuildSkillsInstruction:
    def test_contains_skill_name(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("tdd", description="TDD workflow"))
        try:
            instr = build_skills_instruction()
            assert "tdd" in instr
        finally:
            m._skill_registry = original

    def test_contains_trigger(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("ralplan", trigger="ralplan"))
        try:
            instr = build_skills_instruction()
            assert "ralplan" in instr
        finally:
            m._skill_registry = original

    def test_contains_path(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("tdd"))
        try:
            instr = build_skills_instruction()
            # Accept either Unix or Windows path separators
            assert "tdd" in instr and "SKILL.md" in instr
        finally:
            m._skill_registry = original

    def test_multiple_skills_all_included(self):
        import backend.core.skills as m
        original, _ = _patched_registry(
            _skill("tdd"), _skill("ralplan"), _skill("security")
        )
        try:
            instr = build_skills_instruction()
            assert "tdd" in instr
            assert "ralplan" in instr
            assert "security" in instr
        finally:
            m._skill_registry = original

    def test_returns_empty_when_no_skills(self):
        import backend.core.skills as m
        original, _ = _patched_registry()
        try:
            instr = build_skills_instruction()
            assert instr == ""
        finally:
            m._skill_registry = original

    def test_mentions_read_tool_instruction(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("tdd"))
        try:
            instr = build_skills_instruction()
            assert "Read" in instr or "read" in instr.lower()
        finally:
            m._skill_registry = original


# ---------------------------------------------------------------------------
# match_trigger
# ---------------------------------------------------------------------------


class TestMatchTrigger:
    def test_exact_trigger_matches(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("tdd", trigger="tdd"))
        try:
            matches = match_trigger("run tdd tests")
            assert any(s.name == "tdd" for s in matches)
        finally:
            m._skill_registry = original

    def test_no_trigger_match_returns_empty(self):
        import backend.core.skills as m
        original, _ = _patched_registry(_skill("tdd", trigger="tdd"))
        try:
            matches = match_trigger("completely unrelated task")
            assert matches == []
        finally:
            m._skill_registry = original

    def test_multiple_triggers_can_match(self):
        import backend.core.skills as m
        original, _ = _patched_registry(
            _skill("tdd", trigger="tdd"),
            _skill("ralplan", trigger="ralplan"),
        )
        try:
            matches = match_trigger("tdd ralplan both here")
            names = [s.name for s in matches]
            assert "tdd" in names
            assert "ralplan" in names
        finally:
            m._skill_registry = original

    def test_trigger_with_slash_stripped(self):
        import backend.core.skills as m
        skill = _skill("tdd", trigger="/tdd")
        original, _ = _patched_registry(skill)
        try:
            # Text without slash should still match after stripping
            matches = match_trigger("run tdd tests")
            assert any(s.name == "tdd" for s in matches)
        finally:
            m._skill_registry = original


# ---------------------------------------------------------------------------
# Prompt injection via SkillSelector
# ---------------------------------------------------------------------------


class TestSkillSelectorPromptInjection:
    """Verify that skill content can be injected into a prompt context."""

    SKILLS_ROOT = Path(__file__).parent.parent.parent / "skills"

    def test_matched_skill_has_raw_content(self):
        from backend.core.skills import discover_skills
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        sel = SkillSelector()
        m = sel.select("ralplan consensus plan", registry=reg)
        if m.matched and m.skill:
            # raw content should be usable for prompt injection
            assert len(m.skill.raw) > 0

    def test_no_match_does_not_raise(self):
        sel = SkillSelector()
        reg = SkillRegistry()  # empty
        # Should never raise
        m = sel.select("xyz abc completely unknown")
        assert isinstance(m, SkillMatch)

    def test_matched_skill_path_exists_for_known_skills(self):
        from backend.core.skills import discover_skills
        reg = SkillRegistry()
        discover_skills(reg, paths=[self.SKILLS_ROOT])
        sel = SkillSelector()
        m = sel.select("ralplan consensus", registry=reg)
        if m.matched and m.skill:
            assert m.skill.path.exists()


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


class TestSkillFallback:
    def test_select_with_empty_registry_is_safe(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        m = sel.select("some random task", registry=reg)
        assert not m.matched
        assert m.skill is None
        assert m.confidence == 0.0

    def test_select_many_empty_registry(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        result = sel.select_many("some task", registry=reg)
        assert result == []

    def test_match_trigger_empty_registry(self):
        import backend.core.skills as mod
        original, _ = _patched_registry()
        try:
            matches = match_trigger("any text")
            assert matches == []
        finally:
            mod._skill_registry = original

    def test_skill_match_none_safe(self):
        m = SkillMatch(skill=None, skill_name="", confidence=0.0, reason="fallback")
        assert not m.matched
        assert m.skill is None

    def test_selector_confidence_threshold_default(self):
        sel = SkillSelector()
        assert 0 < sel.CONFIDENCE_THRESHOLD < 1.0


# ---------------------------------------------------------------------------
# Trace observability
# ---------------------------------------------------------------------------


class TestTraceObservability:
    def test_multiple_selects_all_traced(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        reg.register(_skill("tdd", trigger="tdd"))
        reg.register(_skill("ralplan", trigger="ralplan"))
        sel.select("tdd tests", registry=reg)
        sel.select("ralplan plan", registry=reg)
        sel.select("unknown xyz", registry=reg)
        trace = sel.get_trace()
        assert len(trace) >= 3

    def test_trace_entry_has_timestamp(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        reg.register(_skill("tdd", trigger="tdd"))
        sel.select("tdd tests", registry=reg)
        entry = sel.get_trace()[0]
        assert entry.timestamp is not None

    def test_trace_entry_confidence_matches_match(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        reg.register(_skill("tdd", trigger="tdd"))
        m = sel.select("tdd tests for auth", registry=reg)
        entry = sel.get_trace()[0]
        assert abs(entry.confidence - m.confidence) < 0.001

    def test_trace_capped_at_200(self):
        sel = SkillSelector()
        reg = SkillRegistry()
        for i in range(250):
            sel.select(f"task {i}", registry=reg)
        # internal deque is bounded at 200
        all_entries = sel.get_trace(limit=300)
        assert len(all_entries) <= 200
