"""Team Pipeline — orchestrate specialized agents with auto-fix loop.

Stages: Oracle (research) → Metis (plan) → Sisyphus (exec)
      → Momus (verify) ↔ Fixer (fix, max 3x) → Sentinel (security)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator, Callable, Awaitable

from backend.agents.handler import agent_handler
from backend.memory.wisdom import WisdomItem, wisdom_store
from backend.orchestration.plan_store import PlanStatus, plan_store
from backend.schemas.ws import WSAgentSwitch, WSError, WSNotification, WSPipelineStage, WSThinkingProgress, WSTurnEnd
from backend.services.notifications import (
    NotificationCategory,
    NotificationLevel,
    notification_service,
)

logger = logging.getLogger("tenderclaw.orchestration.pipeline")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
MAX_FIX_ATTEMPTS = 3


class TeamPipeline:

    STAGE_PHASES = {
        "oracle": "analyzing",
        "metis": "planning",
        "sisyphus": "reasoning",
        "momus": "analyzing",
        "fixer": "reasoning",
        "sentinel": "analyzing",
    }

    async def _notify_stage(
        self,
        send: SendFn,
        agent_name: str,
        status: str,
        detail: str,
        session_id: str = "unknown",
    ) -> None:
        """Emit pipeline stage + thinking progress + notification for the HUD."""
        await send(WSPipelineStage(stage=agent_name, status=status, detail=detail).model_dump())
        await send(WSAgentSwitch(agent_name=agent_name, task=detail).model_dump())

        # Thinking progress for the HUD thinking indicator
        phase = self.STAGE_PHASES.get(agent_name, "reasoning")
        if status == "started":
            await send(WSThinkingProgress(
                agent_name=agent_name, phase=phase, progress_pct=0, detail=detail,
            ).model_dump())
        elif status in ("completed", "failed"):
            await send(WSThinkingProgress(
                agent_name=agent_name, phase=phase, progress_pct=100, detail=detail,
            ).model_dump())

        if status == "started":
            notif = notification_service.create(
                title=f"{agent_name.capitalize()} started",
                body=detail,
                level=NotificationLevel.INFO,
                category=NotificationCategory.PIPELINE,
                agent_name=agent_name,
                session_id=session_id,
                auto_dismiss_ms=4000,
            )
            await send(WSNotification(
                id=notif.id,
                level=notif.level.value,
                category=notif.category.value,
                title=notif.title,
                body=notif.body,
                agent_name=notif.agent_name,
                auto_dismiss_ms=notif.auto_dismiss_ms,
            ).model_dump())
        elif status == "failed":
            notif = notification_service.create(
                title=f"{agent_name.capitalize()} failed",
                body=detail,
                level=NotificationLevel.ERROR,
                category=NotificationCategory.PIPELINE,
                agent_name=agent_name,
                session_id=session_id,
            )
            await send(WSNotification(
                id=notif.id,
                level=notif.level.value,
                category=notif.category.value,
                title=notif.title,
                body=notif.body,
                agent_name=notif.agent_name,
                auto_dismiss_ms=notif.auto_dismiss_ms,
            ).model_dump())

    async def run_implement_pipeline(
        self,
        task: str,
        messages: list[dict[str, Any]],
        send: SendFn,
        session: Any = None,  # SessionData | None — for abort checks
    ) -> AsyncIterator[dict[str, Any]]:
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:8]}"
        session_id = getattr(session, "session_id", "unknown")
        all_issues: list[str] = []

        def aborted() -> bool:
            return bool(session and session.should_abort)

        # Stage 1: Research
        logger.info("[%s] Stage 1: Oracle (research)", pipeline_id)
        await send(WSPipelineStage(stage="oracle", status="started", detail="Researching codebase").model_dump())
        await send(WSAgentSwitch(agent_name="oracle", task="research").model_dump())
        research = await self._run_agent(
            "oracle",
            messages,
            f"Research the codebase for: {task}. Identify dependencies, constraints, risks.",
            send,
        )
        if aborted():
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Inject relevant wisdom + past plans into planning context
        wisdom_ctx = _format_wisdom(wisdom_store.find_relevant(task))
        past_plans_ctx = plan_store.format_similar_for_prompt(task)

        await send(WSPipelineStage(stage="oracle", status="completed").model_dump())

        # Stage 2: Planning
        logger.info("[%s] Stage 2: Metis (planning)", pipeline_id)
        await send(WSPipelineStage(stage="metis", status="started", detail="Creating implementation plan").model_dump())
        await send(WSAgentSwitch(agent_name="metis", task="planning").model_dump())
        plan_content = await self._run_agent(
            "metis",
            messages,
            f"Create a detailed implementation plan for: {task}\n\nResearch:\n{research}{wisdom_ctx}{past_plans_ctx}",
            send,
        )
        if aborted():
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Checkpoint plan
        stored_plan = plan_store.create(
            session_id=session_id,
            task=task,
            plan_content=plan_content,
            pipeline_id=pipeline_id,
            research_summary=research[:500],
        )
        plan_store.update_status(stored_plan.plan_id, PlanStatus.ACTIVE)

        await send(WSPipelineStage(stage="metis", status="completed").model_dump())

        # Stage 3: Execution
        logger.info("[%s] Stage 3: Sisyphus (execution)", pipeline_id)
        await send(WSPipelineStage(stage="sisyphus", status="started", detail="Implementing changes").model_dump())
        await send(WSAgentSwitch(agent_name="sisyphus", task="implementing").model_dump())
        plan_store.update_status(stored_plan.plan_id, PlanStatus.EXECUTING)
        async for part in agent_handler.execute_agent_turn(
            "sisyphus",
            messages + [{"role": "user", "content": f"Execute this plan:\n{plan_content}\n\nUse tools to implement."}],
        ):
            if part.get("type") == "assistant_text":
                yield part
        if aborted():
            plan_store.update_status(stored_plan.plan_id, PlanStatus.ABANDONED)
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        await send(WSPipelineStage(stage="sisyphus", status="completed").model_dump())

        # Stages 4-5: Verify → Fix loop
        plan_store.update_status(stored_plan.plan_id, PlanStatus.VERIFYING)
        for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            if aborted():
                plan_store.update_status(stored_plan.plan_id, PlanStatus.ABANDONED)
                yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
                return

            logger.info("[%s] Stage 4: Momus (verify, attempt %d)", pipeline_id, attempt)
            await send(WSPipelineStage(stage="momus", status="started", detail=f"Verifying (attempt {attempt})").model_dump())
            await send(WSAgentSwitch(agent_name="momus", task="verifying").model_dump())
            verification = await self._run_agent(
                "momus",
                messages,
                _verify_prompt(task, all_issues),
                send,
            )
            issues = _extract_issues(verification)

            if not issues:
                logger.info("[%s] Verification passed", pipeline_id)
                await send(WSPipelineStage(stage="momus", status="completed", detail="All checks passed").model_dump())
                break

            all_issues.extend(issues)
            plan_store.record_fix_attempt(stored_plan.plan_id, issues)

            await send(WSPipelineStage(stage="momus", status="completed", detail=f"{len(issues)} issues found").model_dump())

            if attempt == MAX_FIX_ATTEMPTS:
                logger.warning("[%s] Max fix attempts reached", pipeline_id)
                await send(WSPipelineStage(stage="fixer", status="failed", detail="Max attempts reached").model_dump())
                plan_store.update_status(
                    stored_plan.plan_id,
                    PlanStatus.FAILED,
                    issues=issues,
                    metadata={"reason": "max_fix_attempts"},
                )
                yield WSError(
                    error=f"Max fix attempts reached. Remaining issues: {issues}",
                    code="max_fix_attempts",
                ).model_dump()
                break

            logger.info("[%s] Stage 5: Fixer (attempt %d)", pipeline_id, attempt)
            await send(WSPipelineStage(stage="fixer", status="started", detail=f"Fix attempt {attempt}").model_dump())
            await send(WSAgentSwitch(agent_name="fixer", task=f"fixing (attempt {attempt})").model_dump())
            async for part in agent_handler.execute_agent_turn(
                "fixer",
                messages + [{"role": "user", "content": _fix_prompt(issues)}],
            ):
                if part.get("type") == "assistant_text":
                    yield part

        if aborted():
            plan_store.update_status(stored_plan.plan_id, PlanStatus.ABANDONED)
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Stage 6: Security audit
        logger.info("[%s] Stage 6: Sentinel (security)", pipeline_id)
        await send(WSPipelineStage(stage="sentinel", status="started", detail="Security audit").model_dump())
        await send(WSAgentSwitch(agent_name="sentinel", task="security audit").model_dump())
        async for part in agent_handler.execute_agent_turn(
            "sentinel",
            messages + [{"role": "user", "content": _security_prompt(task)}],
        ):
            if part.get("type") == "assistant_text":
                yield part

        await send(WSPipelineStage(stage="sentinel", status="completed").model_dump())

        # Record wisdom + finalize plan
        _record_wisdom(task, plan_content, all_issues)
        score = 1.0 if not all_issues else max(0.3, 1.0 - len(all_issues) * 0.1)
        plan_store.complete(stored_plan.plan_id, success_score=score)

        await send(WSAgentSwitch(agent_name="sisyphus", task="complete").model_dump())
        yield WSTurnEnd(stop_reason="pipeline_complete").model_dump()

    async def _run_agent(
        self,
        agent_name: str,
        base_messages: list[dict],
        prompt: str,
        send: SendFn,
    ) -> str:
        parts: list[str] = []
        async for part in agent_handler.execute_agent_turn(
            agent_name,
            base_messages + [{"role": "user", "content": prompt}],
        ):
            if part.get("type") == "assistant_text":
                parts.append(part.get("delta", ""))
        return "".join(parts)


# --- Helpers ---

def _format_wisdom(items: list[WisdomItem]) -> str:
    if not items:
        return ""
    lines = ["\n\n## Relevant Past Experience"]
    for item in items[:3]:
        lines.append(f"- {item.task_type}: {item.description}")
        lines.append(f"  Pattern: {item.solution_pattern}")
    return "\n".join(lines)


def _verify_prompt(task: str, prior_issues: list[str]) -> str:
    prior = "\n".join(f"- {i}" for i in prior_issues) if prior_issues else "None"
    return f"""Verify the implementation for: {task}

Prior issues already fixed:
{prior}

Check correctness, code quality, edge cases, and performance.
Respond with JSON: {{"issues": ["..."], "status": "pass|fail"}}"""


def _fix_prompt(issues: list[str]) -> str:
    return "Fix these issues using tools:\n" + "\n".join(f"- {i}" for i in issues)


def _security_prompt(task: str) -> str:
    return f"""Security audit for: {task}
Check: SQL injection, XSS, auth/authz issues, data exposure, dependency vulnerabilities."""


def _extract_issues(text: str) -> list[str]:
    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.index("```", start)
            data = json.loads(text[start:end].strip())
            issues = data.get("issues", [])
            if data.get("status") == "pass":
                return []
            return [i for i in issues if i]
        except (ValueError, json.JSONDecodeError):
            pass

    # Fallback: look for explicit issue markers
    return [
        line.strip().lstrip("-*").strip()
        for line in text.splitlines()
        if any(kw in line.lower() for kw in ("issue", "problem", "bug", "error", "fail"))
        and len(line.strip()) > 10
    ]


def _record_wisdom(task: str, plan: str, issues: list[str]) -> None:
    try:
        wisdom_store.add(WisdomItem(
            id=f"w_{uuid.uuid4().hex[:8]}",
            task_type="implementation",
            description=task[:200],
            solution_pattern=plan[:150],
            success_score=1.0 if not issues else 0.7,
        ))
    except Exception as exc:
        logger.warning("Failed to record wisdom: %s", exc)


team_pipeline = TeamPipeline()
