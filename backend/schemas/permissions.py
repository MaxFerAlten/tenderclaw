"""Permission schemas — security model for tool execution."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tool call lifecycle state machine
# ---------------------------------------------------------------------------


class ToolCallState(str, Enum):
    """Explicit state for a single tool call — observable end-to-end.

    Transitions:
        REQUESTED → APPROVED → RUNNING → COMPLETED
        REQUESTED → DENIED
        RUNNING   → FAILED
    """

    REQUESTED = "requested"   # Tool call received, permission check pending
    APPROVED = "approved"     # User/policy approved, waiting to execute
    DENIED = "denied"         # Blocked by policy or user rejection
    RUNNING = "running"       # Currently executing
    COMPLETED = "completed"   # Finished successfully
    FAILED = "failed"         # Execution threw an exception


class PendingToolCall(BaseModel):
    """Serializable record of an in-flight or recently resolved tool call."""

    tool_use_id: str
    tool_name: str
    state: ToolCallState = ToolCallState.REQUESTED
    input: dict[str, Any] = Field(default_factory=dict)
    result_preview: str = ""          # First 200 chars of result (for resume context)
    is_error: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None

    def transition(self, new_state: ToolCallState, result_preview: str = "", is_error: bool = False) -> None:
        self.state = new_state
        if result_preview:
            self.result_preview = result_preview[:200]
        self.is_error = is_error
        if new_state in (ToolCallState.COMPLETED, ToolCallState.FAILED, ToolCallState.DENIED):
            self.resolved_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Permission policy
# ---------------------------------------------------------------------------


class PermissionMode(str, Enum):
    """How the system decides whether to allow tool execution."""

    DEFAULT = "default"      # Ask user for medium/high risk
    AUTO = "auto"            # ML classifier auto-approves (like YOLO)
    PLAN = "plan"            # Read-only tools only, no writes
    TRUST = "trust"          # Approve everything (dangerous)


class PermissionDecision(str, Enum):
    """Result of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionRule(BaseModel):
    """A single permission rule."""

    tool_name: str = "*"
    pattern: str = "*"       # Glob for tool input (e.g., file path)
    decision: PermissionDecision = PermissionDecision.ASK


class PermissionConfig(BaseModel):
    """Permission system configuration."""

    mode: PermissionMode = PermissionMode.DEFAULT
    always_allow: list[PermissionRule] = []
    always_deny: list[PermissionRule] = []


class ToolPermissionPolicy(BaseModel):
    """Unified permission policy per tool or risk level.

    Evaluated in order:
      1. Tool-specific rules (always_deny / always_allow)
      2. Risk-level rules
      3. Mode default

    Use `build_default()` to get a sensible baseline policy.
    """

    config: PermissionConfig = Field(default_factory=PermissionConfig)
    # Risk-level overrides: maps RiskLevel value → desired decision
    risk_overrides: dict[str, PermissionDecision] = Field(default_factory=dict)

    @classmethod
    def build_default(cls) -> "ToolPermissionPolicy":
        """Default policy: deny nothing explicitly, ask for high-risk."""
        return cls(
            config=PermissionConfig(mode=PermissionMode.DEFAULT),
            risk_overrides={
                "high": PermissionDecision.ASK,
                "medium": PermissionDecision.ASK,
                "low": PermissionDecision.ALLOW,
                "none": PermissionDecision.ALLOW,
            },
        )

    @classmethod
    def build_strict(cls) -> "ToolPermissionPolicy":
        """Strict policy: ask for everything except explicitly allowed tools."""
        return cls(
            config=PermissionConfig(mode=PermissionMode.DEFAULT),
            risk_overrides={
                "high": PermissionDecision.ASK,
                "medium": PermissionDecision.ASK,
                "low": PermissionDecision.ASK,
                "none": PermissionDecision.ALLOW,
            },
        )

    @classmethod
    def build_trust(cls) -> "ToolPermissionPolicy":
        """Trust policy: allow everything (use in sandboxed/test environments)."""
        return cls(
            config=PermissionConfig(mode=PermissionMode.TRUST),
            risk_overrides={},
        )
