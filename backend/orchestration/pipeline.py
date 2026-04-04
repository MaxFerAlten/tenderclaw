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
from backend.schemas.ws import WSAgentSwitch, WSError, WSTurnEnd

logger = logging.getLogger("tenderclaw.orchestration.pipeline")

SendFn = Callable[[dict[str, Any]], Awaitable[None]]
MAX_FIX_ATTEMPTS = 3


class TeamPipeline:

    async def run_implement_pipeline(
        self,
        task: str,
        messages: list[dict[str, Any]],
        send: SendFn,
        session: Any = None,  # SessionData | None — for abort checks
    ) -> AsyncIterator[dict[str, Any]]:
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:8]}"
        all_issues: list[str] = []

        def aborted() -> bool:
            return bool(session and session.should_abort)

        # Stage 1: Research
        logger.info("[%s] Stage 1: Oracle (research)", pipeline_id)
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

        # Inject relevant wisdom into planning context
        wisdom_ctx = _format_wisdom(wisdom_store.find_relevant(task))

        # Stage 2: Planning
        logger.info("[%s] Stage 2: Metis (planning)", pipeline_id)
        await send(WSAgentSwitch(agent_name="metis", task="planning").model_dump())
        plan = await self._run_agent(
            "metis",
            messages,
            f"Create a detailed implementation plan for: {task}\n\nResearch:\n{research}{wisdom_ctx}",
            send,
        )
        if aborted():
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Stage 3: Execution
        logger.info("[%s] Stage 3: Sisyphus (execution)", pipeline_id)
        await send(WSAgentSwitch(agent_name="sisyphus", task="implementing").model_dump())
        async for part in agent_handler.execute_agent_turn(
            "sisyphus",
            messages + [{"role": "user", "content": f"Execute this plan:\n{plan}\n\nUse tools to implement."}],
        ):
            if part.get("type") == "assistant_text":
                yield part
        if aborted():
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Stages 4-5: Verify → Fix loop
        for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            if aborted():
                yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
                return

            logger.info("[%s] Stage 4: Momus (verify, attempt %d)", pipeline_id, attempt)
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
                break

            all_issues.extend(issues)

            if attempt == MAX_FIX_ATTEMPTS:
                logger.warning("[%s] Max fix attempts reached", pipeline_id)
                yield WSError(
                    error=f"Max fix attempts reached. Remaining issues: {issues}",
                    code="max_fix_attempts",
                ).model_dump()
                break

            logger.info("[%s] Stage 5: Fixer (attempt %d)", pipeline_id, attempt)
            await send(WSAgentSwitch(agent_name="fixer", task=f"fixing (attempt {attempt})").model_dump())
            async for part in agent_handler.execute_agent_turn(
                "fixer",
                messages + [{"role": "user", "content": _fix_prompt(issues)}],
            ):
                if part.get("type") == "assistant_text":
                    yield part

        if aborted():
            yield WSError(error="Pipeline aborted by user", code="aborted").model_dump()
            return

        # Stage 6: Security audit
        logger.info("[%s] Stage 6: Sentinel (security)", pipeline_id)
        await send(WSAgentSwitch(agent_name="sentinel", task="security audit").model_dump())
        async for part in agent_handler.execute_agent_turn(
            "sentinel",
            messages + [{"role": "user", "content": _security_prompt(task)}],
        ):
            if part.get("type") == "assistant_text":
                yield part

        # Record wisdom
        _record_wisdom(task, plan, all_issues)

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
