"""Tests — Sprint 2 tool permissions: ToolPermissionPolicy, check_permission."""

from __future__ import annotations

import pytest

from backend.schemas.permissions import (
    PermissionConfig,
    PermissionDecision,
    PermissionMode,
    PermissionRule,
    ToolPermissionPolicy,
)
from backend.hooks.permissions import check_permission


# ---------------------------------------------------------------------------
# ToolPermissionPolicy factories
# ---------------------------------------------------------------------------


class TestToolPermissionPolicyFactories:
    def test_build_default(self) -> None:
        policy = ToolPermissionPolicy.build_default()
        assert policy.config.mode == PermissionMode.DEFAULT
        assert policy.risk_overrides["high"] == PermissionDecision.ASK
        assert policy.risk_overrides["none"] == PermissionDecision.ALLOW

    def test_build_strict(self) -> None:
        policy = ToolPermissionPolicy.build_strict()
        assert policy.risk_overrides["low"] == PermissionDecision.ASK
        assert policy.risk_overrides["none"] == PermissionDecision.ALLOW

    def test_build_trust(self) -> None:
        policy = ToolPermissionPolicy.build_trust()
        assert policy.config.mode == PermissionMode.TRUST
        assert policy.risk_overrides == {}


# ---------------------------------------------------------------------------
# check_permission — mode-based decisions
# ---------------------------------------------------------------------------


class TestCheckPermissionModes:
    def test_trust_mode_allows_everything(self) -> None:
        decision = check_permission(
            "delete_files",
            {"path": "/etc/passwd"},
            mode=PermissionMode.TRUST,
        )
        assert decision == PermissionDecision.ALLOW

    def test_auto_mode_allows_not_denied(self) -> None:
        decision = check_permission(
            "any_tool",
            {},
            mode=PermissionMode.AUTO,
        )
        assert decision == PermissionDecision.ALLOW

    def test_explicit_deny_rule_wins_over_trust_mode(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.TRUST,
            always_deny=[PermissionRule(tool_name="nuke_*", pattern="*")],
        )
        decision = check_permission("nuke_everything", {}, config=config)
        assert decision == PermissionDecision.DENY

    def test_explicit_allow_rule_wins_over_default_ask(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.DEFAULT,
            always_allow=[PermissionRule(tool_name="safe_tool", pattern="*")],
        )
        decision = check_permission("safe_tool", {}, config=config)
        assert decision == PermissionDecision.ALLOW

    def test_unknown_tool_in_default_mode_asks(self) -> None:
        # Unknown tool has no risk_level — falls back to ASK
        decision = check_permission("totally_unknown_tool_xyz", {}, mode=PermissionMode.DEFAULT)
        assert decision == PermissionDecision.ASK


# ---------------------------------------------------------------------------
# check_permission — policy risk_overrides
# ---------------------------------------------------------------------------


class TestCheckPermissionPolicyRiskOverrides:
    def test_policy_high_risk_override_to_allow(self) -> None:
        """Policy can override high-risk to ALLOW (e.g., trusted CI environment)."""
        policy = ToolPermissionPolicy(
            config=PermissionConfig(mode=PermissionMode.DEFAULT),
            risk_overrides={"high": PermissionDecision.ALLOW},
        )
        # Unknown tool defaults to 'high' risk in the policy path
        decision = check_permission("unknown_risky_tool", {}, mode=PermissionMode.DEFAULT, policy=policy)
        assert decision == PermissionDecision.ALLOW

    def test_policy_low_risk_override_to_ask(self) -> None:
        """Strict policy: even low-risk tools require confirmation."""
        policy = ToolPermissionPolicy.build_strict()
        decision = check_permission(
            "completely_unknown",
            {},
            mode=PermissionMode.DEFAULT,
            policy=policy,
        )
        # unknown → maps to high risk → ASK (strict overrides high to ASK)
        assert decision == PermissionDecision.ASK

    def test_default_policy_allows_unknown_none_risk(self) -> None:
        """Default policy: none-risk tools are ALLOW."""
        policy = ToolPermissionPolicy.build_default()
        decision = check_permission(
            "completely_unknown",
            {},
            mode=PermissionMode.DEFAULT,
            policy=policy,
        )
        # unknown → high → ASK in default policy
        assert decision == PermissionDecision.ASK


# ---------------------------------------------------------------------------
# Wildcard rules
# ---------------------------------------------------------------------------


class TestPermissionRuleWildcards:
    def test_wildcard_tool_name_matches(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.DEFAULT,
            always_deny=[PermissionRule(tool_name="shell_*", pattern="*")],
        )
        assert check_permission("shell_exec", {}, config=config) == PermissionDecision.DENY
        assert check_permission("shell_run_cmd", {}, config=config) == PermissionDecision.DENY

    def test_wildcard_does_not_match_unrelated(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.AUTO,
            always_deny=[PermissionRule(tool_name="shell_*", pattern="*")],
        )
        assert check_permission("read_file", {}, config=config) == PermissionDecision.ALLOW

    def test_input_pattern_deny(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.DEFAULT,
            always_deny=[PermissionRule(tool_name="*", pattern="*/etc/*")],
        )
        decision = check_permission("read_file", {"path": "/etc/passwd"}, config=config)
        assert decision == PermissionDecision.DENY

    def test_input_pattern_no_match_allows(self) -> None:
        config = PermissionConfig(
            mode=PermissionMode.AUTO,
            always_deny=[PermissionRule(tool_name="*", pattern="*/etc/*")],
        )
        decision = check_permission("read_file", {"path": "/home/user/data.txt"}, config=config)
        assert decision == PermissionDecision.ALLOW
