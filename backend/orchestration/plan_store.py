"""PlanStore — persist and retrieve implementation plans as JSON checkpoints.

Follows the same in-memory + disk persistence pattern as SessionStore
and WisdomStore. Plans are created by the Metis stage of the pipeline
and consumed by Sisyphus for execution.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("tenderclaw.orchestration.plan_store")

PLANS_DIR = Path(".tenderclaw/state/plans")


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class PlanStep(BaseModel):
    """A single step within a plan."""

    index: int
    description: str
    status: str = "pending"  # pending | in_progress | done | skipped
    agent: str | None = None
    notes: str | None = None


class Plan(BaseModel):
    """A persisted implementation plan with lifecycle tracking."""

    plan_id: str
    session_id: str
    pipeline_id: str | None = None
    task: str
    status: PlanStatus = PlanStatus.DRAFT
    plan_content: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    research_summary: str = ""
    issues: list[str] = Field(default_factory=list)
    fix_attempts: int = 0
    success_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format plan for injection into agent prompts."""
        lines = [f"## Plan: {self.task[:120]}"]
        lines.append(f"Status: {self.status.value} | Steps: {len(self.steps)}")
        if self.plan_content:
            lines.append(f"\n{self.plan_content}")
        if self.steps:
            lines.append("\n### Steps")
            for step in self.steps:
                marker = {"done": "[x]", "in_progress": "[>]", "skipped": "[-]"}.get(
                    step.status, "[ ]"
                )
                lines.append(f"{marker} {step.index}. {step.description}")
        if self.issues:
            lines.append("\n### Issues Found")
            for issue in self.issues:
                lines.append(f"- {issue}")
        return "\n".join(lines)


class PlanStore:
    """In-memory store for plans with JSON disk persistence."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._storage = storage_path or PLANS_DIR
        self._storage.mkdir(parents=True, exist_ok=True)
        self._plans: dict[str, Plan] = {}
        self._load_all()

    # --- CRUD ---

    def create(
        self,
        session_id: str,
        task: str,
        plan_content: str = "",
        *,
        pipeline_id: str | None = None,
        research_summary: str = "",
    ) -> Plan:
        """Create and persist a new plan."""
        plan = Plan(
            plan_id=f"plan_{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            pipeline_id=pipeline_id,
            task=task[:500],
            plan_content=plan_content,
            research_summary=research_summary,
            steps=_parse_steps(plan_content),
            tags=_suggest_tags(task),
        )
        self._plans[plan.plan_id] = plan
        self._save(plan)
        logger.info("Plan created: %s for session %s", plan.plan_id, session_id)
        return plan

    def get(self, plan_id: str) -> Plan | None:
        """Get plan by ID (memory first, then disk)."""
        plan = self._plans.get(plan_id)
        if plan is not None:
            return plan
        path = self._storage / f"{plan_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                plan = Plan.model_validate(data)
                self._plans[plan_id] = plan
                return plan
            except Exception as exc:
                logger.error("Failed to load plan %s: %s", plan_id, exc)
        return None

    def list_for_session(self, session_id: str) -> list[Plan]:
        """List all plans for a session, ordered by creation time."""
        plans = [p for p in self._plans.values() if p.session_id == session_id]
        plans.sort(key=lambda p: p.created_at)
        return plans

    def list_recent(self, limit: int = 10) -> list[Plan]:
        """List most recent plans across all sessions."""
        plans = sorted(self._plans.values(), key=lambda p: p.created_at, reverse=True)
        return plans[:limit]

    def delete(self, plan_id: str) -> bool:
        """Delete plan from memory and disk."""
        removed = self._plans.pop(plan_id, None)
        path = self._storage / f"{plan_id}.json"
        path.unlink(missing_ok=True)
        if removed:
            logger.info("Plan deleted: %s", plan_id)
        return removed is not None

    # --- Lifecycle transitions ---

    def update_status(
        self,
        plan_id: str,
        status: PlanStatus,
        *,
        issues: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Plan | None:
        """Transition plan status and persist."""
        plan = self.get(plan_id)
        if plan is None:
            return None
        plan.status = status
        plan.updated_at = datetime.now()
        if issues is not None:
            plan.issues.extend(issues)
        if metadata:
            plan.metadata.update(metadata)
        if status in (PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.ABANDONED):
            plan.completed_at = datetime.now()
        self._save(plan)
        logger.info("Plan %s -> %s", plan_id, status.value)
        return plan

    def mark_step(self, plan_id: str, step_index: int, status: str) -> Plan | None:
        """Mark a specific step's status."""
        plan = self.get(plan_id)
        if plan is None:
            return None
        for step in plan.steps:
            if step.index == step_index:
                step.status = status
                break
        plan.updated_at = datetime.now()
        self._save(plan)
        return plan

    def record_fix_attempt(self, plan_id: str, issues: list[str]) -> Plan | None:
        """Record a fix attempt and its issues."""
        plan = self.get(plan_id)
        if plan is None:
            return None
        plan.fix_attempts += 1
        plan.issues.extend(issues)
        plan.updated_at = datetime.now()
        self._save(plan)
        return plan

    def complete(self, plan_id: str, success_score: float = 1.0) -> Plan | None:
        """Mark plan as completed with a success score."""
        plan = self.get(plan_id)
        if plan is None:
            return None
        plan.status = PlanStatus.COMPLETED
        plan.success_score = success_score
        plan.completed_at = datetime.now()
        plan.updated_at = datetime.now()
        # Mark remaining pending steps as skipped
        for step in plan.steps:
            if step.status == "pending":
                step.status = "skipped"
        self._save(plan)
        logger.info("Plan completed: %s (score=%.2f)", plan_id, success_score)
        return plan

    # --- Retrieval ---

    def find_similar(self, task: str, limit: int = 3) -> list[Plan]:
        """Find past plans for similar tasks (keyword matching)."""
        query_words = set(re.findall(r"\w+", task.lower()))
        scored: list[tuple[float, Plan]] = []

        for plan in self._plans.values():
            if plan.status not in (PlanStatus.COMPLETED, PlanStatus.FAILED):
                continue
            plan_words = set(re.findall(r"\w+", plan.task.lower()))
            overlap = len(query_words & plan_words)
            if overlap == 0:
                continue
            score = overlap * 0.5
            # Boost completed+successful plans
            if plan.status == PlanStatus.COMPLETED:
                score += plan.success_score
            # Tag match
            for tag in plan.tags:
                if tag.lower() in task.lower():
                    score += 0.5
            # Recency bonus
            days_old = (datetime.now() - plan.created_at).days
            score += max(0, 1.0 - days_old / 30)
            scored.append((score, plan))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def format_similar_for_prompt(self, task: str) -> str:
        """Find and format similar past plans for prompt injection."""
        similar = self.find_similar(task)
        if not similar:
            return ""
        lines = ["\n## Past Plans for Similar Tasks"]
        for plan in similar:
            status_icon = "ok" if plan.status == PlanStatus.COMPLETED else "fail"
            lines.append(
                f"- [{status_icon}] {plan.task[:100]} "
                f"(score={plan.success_score:.1f}, issues={len(plan.issues)})"
            )
            if plan.steps:
                lines.append(f"  Steps: {len(plan.steps)}")
        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Get plan store statistics."""
        plans = list(self._plans.values())
        by_status: dict[str, int] = {}
        for p in plans:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
        completed = [p for p in plans if p.status == PlanStatus.COMPLETED]
        return {
            "total": len(plans),
            "by_status": by_status,
            "avg_success_score": (
                sum(p.success_score for p in completed) / len(completed)
                if completed
                else 0
            ),
            "avg_fix_attempts": (
                sum(p.fix_attempts for p in completed) / len(completed)
                if completed
                else 0
            ),
            "avg_steps": (
                sum(len(p.steps) for p in plans) / len(plans) if plans else 0
            ),
        }

    # --- Persistence ---

    def _save(self, plan: Plan) -> None:
        path = self._storage / f"{plan.plan_id}.json"
        path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    def _load_all(self) -> None:
        for path in self._storage.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                plan = Plan.model_validate(data)
                self._plans[plan.plan_id] = plan
            except Exception as exc:
                logger.error("Failed to load plan %s: %s", path, exc)
        if self._plans:
            logger.info("Loaded %d plans from disk", len(self._plans))


# --- Helpers ---


def _parse_steps(plan_content: str) -> list[PlanStep]:
    """Extract numbered steps from plan markdown."""
    steps: list[PlanStep] = []
    for match in re.finditer(r"^\s*(\d+)[.)]\s+(.+)$", plan_content, re.MULTILINE):
        steps.append(
            PlanStep(index=int(match.group(1)), description=match.group(2).strip())
        )
    return steps


_TAG_PATTERNS: dict[str, list[str]] = {
    "react": [r"react", r"jsx", r"component"],
    "python": [r"python", r"pydantic", r"fastapi"],
    "typescript": [r"typescript", r"tsx?"],
    "api": [r"api", r"endpoint", r"router"],
    "database": [r"sql", r"database", r"migration"],
    "testing": [r"test", r"pytest", r"coverage"],
    "security": [r"auth", r"security", r"jwt"],
    "refactor": [r"refactor", r"cleanup", r"reorganize"],
}


def _suggest_tags(text: str) -> list[str]:
    tags: list[str] = []
    for tag, patterns in _TAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                tags.append(tag)
                break
    return tags[:5]


# Module-level instance
plan_store = PlanStore()
