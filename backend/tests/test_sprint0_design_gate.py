"""Sprint 0 Tests — Design Gate & Methodology.

Tests verify:
1. brainstorming and writing-plans SKILL.md files exist and are well-formed
2. superpowers_loader correctly parses system skills with `system: true`
3. keyword_detection triggers for brainstorm/design/spec/ralplan keywords
4. SuperpowersPlugin.should_activate_design_gate routes correctly
"""

import pytest
from pathlib import Path

from backend.core.keyword_detection import KeywordDetector
from backend.plugins.superpowers_loader import load_skills_from_markdown, _parse_frontmatter


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
BRAINSTORMING_SKILL = SKILLS_DIR / "brainstorming" / "SKILL.md"
WRITING_PLANS_SKILL = SKILLS_DIR / "writing-plans" / "SKILL.md"


# ===========================================================================
# 1. Skill file existence and structure
# ===========================================================================

class TestSkillFilesExist:
    """Verify that Sprint 0 skill files exist and have correct structure."""

    def test_brainstorming_skill_exists(self):
        assert BRAINSTORMING_SKILL.exists(), "skills/brainstorming/SKILL.md must exist"

    def test_writing_plans_skill_exists(self):
        assert WRITING_PLANS_SKILL.exists(), "skills/writing-plans/SKILL.md must exist"

    def test_brainstorming_has_frontmatter(self):
        content = BRAINSTORMING_SKILL.read_text("utf-8")
        meta, body = _parse_frontmatter(content)
        assert meta.get("name") == "brainstorming"
        assert meta.get("system") == "true"
        assert meta.get("trigger") == "brainstorm"

    def test_writing_plans_has_frontmatter(self):
        content = WRITING_PLANS_SKILL.read_text("utf-8")
        meta, body = _parse_frontmatter(content)
        assert meta.get("name") == "writing-plans"
        assert meta.get("system") == "true"
        assert meta.get("trigger") == "writing-plan"

    def test_brainstorming_contains_hard_gate(self):
        content = BRAINSTORMING_SKILL.read_text("utf-8")
        assert "HARD-GATE" in content, "Brainstorming must enforce HARD-GATE"
        assert "NO CODE MAY BE WRITTEN" in content

    def test_writing_plans_forbids_placeholders(self):
        content = WRITING_PLANS_SKILL.read_text("utf-8")
        assert "placeholder" in content.lower() or "TODO" in content, \
            "Writing-plans must mention placeholder prohibition"
        assert "exact file path" in content.lower() or "Exact file path" in content


# ===========================================================================
# 2. Superpowers loader — system skill parsing
# ===========================================================================

class TestSuperpowersLoaderSystemSkills:
    """Verify that load_skills_from_markdown correctly handles system: true."""

    def test_loads_system_skills(self):
        skills = load_skills_from_markdown(SKILLS_DIR)
        system_skills = [s for s in skills if s.get("system")]
        names = {s["name"] for s in system_skills}
        assert "brainstorming" in names, "brainstorming must be a system skill"
        assert "writing-plans" in names, "writing-plans must be a system skill"

    def test_system_flag_is_boolean(self):
        skills = load_skills_from_markdown(SKILLS_DIR)
        for s in skills:
            assert isinstance(s["system"], bool), f"system flag for {s['name']} must be bool"

    def test_non_system_skills_exist(self):
        skills = load_skills_from_markdown(SKILLS_DIR)
        non_system = [s for s in skills if not s.get("system")]
        assert len(non_system) > 0, "There should be non-system skills too"

    def test_skill_has_required_fields(self):
        skills = load_skills_from_markdown(SKILLS_DIR)
        for s in skills:
            assert "name" in s
            assert "description" in s
            assert "trigger" in s
            assert "path" in s
            assert "raw" in s

    def test_nonexistent_dir_returns_empty(self):
        skills = load_skills_from_markdown(Path("/nonexistent/path"))
        assert skills == []


# ===========================================================================
# 3. Keyword detection — new triggers
# ===========================================================================

class TestKeywordDetectionSprint0:
    """Verify that brainstorm, design, spec, ralplan keywords are detected."""

    def setup_method(self):
        self.detector = KeywordDetector()

    def test_brainstorm_detected(self):
        matches = self.detector.detect("Let's brainstorm this feature")
        actions = [m.action for m in matches]
        assert "brainstorming" in actions

    def test_design_first_detected(self):
        matches = self.detector.detect("I want to design first before coding")
        actions = [m.action for m in matches]
        assert "brainstorming" in actions

    def test_spec_detected(self):
        matches = self.detector.detect("Write a spec for this module")
        actions = [m.action for m in matches]
        assert "brainstorming" in actions

    def test_writing_plan_detected(self):
        matches = self.detector.detect("Create a writing-plan for the refactor")
        actions = [m.action for m in matches]
        assert "writing-plans" in actions

    def test_implementation_plan_detected(self):
        matches = self.detector.detect("I need an implementation plan")
        actions = [m.action for m in matches]
        assert "writing-plans" in actions

    def test_break_it_down_detected(self):
        matches = self.detector.detect("Break it down into small tasks")
        actions = [m.action for m in matches]
        assert "writing-plans" in actions

    def test_ralplan_detected(self):
        matches = self.detector.detect("Use ralplan for consensus")
        actions = [m.action for m in matches]
        assert "ralplan" in actions

    def test_no_false_positive_on_normal_message(self):
        matches = self.detector.detect("Fix the login bug please")
        actions = [m.action for m in matches]
        assert "brainstorming" not in actions
        assert "writing-plans" not in actions
        assert "ralplan" not in actions

    def test_get_triggered_action_brainstorm(self):
        mapping = self.detector.get_triggered_action("Let's brainstorm the API design")
        assert mapping is not None
        assert mapping.action == "brainstorming"
        assert mapping.skill == "brainstorming"

    def test_get_triggered_action_writing_plan(self):
        mapping = self.detector.get_triggered_action("Create an implementation plan")
        assert mapping is not None
        assert mapping.action == "writing-plans"
        assert mapping.skill == "writing-plans"

    def test_extract_task_removes_keyword(self):
        mapping = self.detector.get_triggered_action("brainstorm the new auth system")
        assert mapping is not None
        task = self.detector.extract_task("brainstorm the new auth system", mapping)
        assert "brainstorm" not in task.lower()
        assert "auth system" in task.lower()


# ===========================================================================
# 4. SuperpowersPlugin design gate routing
# ===========================================================================

class TestDesignGateRouting:
    """Verify that should_activate_design_gate routes to correct skills."""

    def setup_method(self):
        from backend.plugins.superpowers import SuperpowersPlugin
        self.plugin = SuperpowersPlugin()
        # Simulate loaded system skills
        self.plugin._system_skills = [
            {
                "name": "brainstorming",
                "trigger": "brainstorm",
                "description": "Design-first HARD-GATE",
                "system": True,
            },
            {
                "name": "writing-plans",
                "trigger": "writing-plan",
                "description": "Bite-sized implementation plans",
                "system": True,
            },
        ]

    def test_routes_brainstorm_keyword(self):
        result = self.plugin.should_activate_design_gate("Let's brainstorm this")
        assert result is not None
        assert result["name"] == "brainstorming"

    def test_routes_design_keyword(self):
        result = self.plugin.should_activate_design_gate("I want to design the API")
        assert result is not None
        assert result["name"] == "brainstorming"

    def test_routes_spec_keyword(self):
        result = self.plugin.should_activate_design_gate("Write a spec for auth")
        assert result is not None
        assert result["name"] == "brainstorming"

    def test_routes_writing_plan_trigger(self):
        result = self.plugin.should_activate_design_gate("Create a writing-plan")
        assert result is not None
        assert result["name"] == "writing-plans"

    def test_routes_implementation_plan(self):
        result = self.plugin.should_activate_design_gate("I need an implementation plan")
        assert result is not None
        assert result["name"] == "writing-plans"

    def test_routes_decompose(self):
        result = self.plugin.should_activate_design_gate("Decompose this into tasks")
        assert result is not None
        assert result["name"] == "writing-plans"

    def test_no_route_for_normal_message(self):
        result = self.plugin.should_activate_design_gate("Fix the login bug")
        assert result is None

    def test_no_route_for_empty_message(self):
        result = self.plugin.should_activate_design_gate("")
        assert result is None

    def test_case_insensitive(self):
        result = self.plugin.should_activate_design_gate("BRAINSTORM this feature")
        assert result is not None
        assert result["name"] == "brainstorming"
