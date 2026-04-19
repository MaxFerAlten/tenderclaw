"""Skills API — REST endpoints for skill discovery, execution, and auto-selection.

Sprint 5 additions:
- POST /select  — auto-select best skill for a task/phase/risk combination
- GET  /trace   — return recent skill selection audit trail
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.skills import get_skill_by_name, list_available_skills, skill_selector

logger = logging.getLogger("tenderclaw.api.skills")

router = APIRouter()


class SkillInfo(BaseModel):
    name: str
    path: str
    description: str
    trigger: str
    agents: list[str]


class SkillDetail(SkillInfo):
    flow: list[str]
    rules: list[str]
    raw: str


class SkillExecuteRequest(BaseModel):
    session_id: str | None = None
    params: dict[str, Any] | None = None


class SkillExecuteResponse(BaseModel):
    success: bool
    message: str
    result: Any = None


class SkillSelectRequest(BaseModel):
    task: str
    phase: str = ""
    risk: str = "medium"
    limit: int = 1  # 1 = best match only; >1 = ranked list


class SkillSelectMatch(BaseModel):
    skill_name: str
    confidence: float
    reason: str
    phase: str
    risk: str
    matched: bool


class SkillSelectResponse(BaseModel):
    matches: list[SkillSelectMatch]
    task_snippet: str


class SkillTraceItem(BaseModel):
    timestamp: str
    task_snippet: str
    phase: str
    risk: str
    skill_name: str
    confidence: float
    reason: str


def _skill_detail_response(name: str) -> dict[str, Any]:
    skill = get_skill_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {
        "name": skill.name,
        "path": str(skill.path),
        "description": skill.description,
        "trigger": skill.trigger,
        "agents": skill.agents,
        "flow": skill.flow,
        "rules": skill.rules,
        "raw": skill.raw,
    }


@router.get("", response_model=list[SkillInfo])
async def list_skills() -> list[dict[str, Any]]:
    """Return all available skills."""
    return list_available_skills()


@router.post("/select", response_model=SkillSelectResponse)
async def select_skill(body: SkillSelectRequest) -> dict[str, Any]:
    """Auto-select the best skill(s) for a task, phase, and risk level.

    Returns a ranked list of :class:`SkillSelectMatch` objects.
    Set ``limit=1`` (default) for best match only.
    """
    if body.limit > 1:
        raw_matches = skill_selector.select_many(
            body.task, phase=body.phase, risk=body.risk, limit=body.limit
        )
        matches = [
            SkillSelectMatch(
                skill_name=m.skill_name,
                confidence=m.confidence,
                reason=m.reason,
                phase=m.phase,
                risk=m.risk,
                matched=m.matched,
            )
            for m in raw_matches
        ]
    else:
        m = skill_selector.select(body.task, phase=body.phase, risk=body.risk)
        matches = [SkillSelectMatch(
            skill_name=m.skill_name,
            confidence=m.confidence,
            reason=m.reason,
            phase=m.phase,
            risk=m.risk,
            matched=m.matched,
        )]

    return {
        "matches": matches,
        "task_snippet": body.task[:120],
    }


@router.get("/trace", response_model=list[SkillTraceItem])
async def get_skill_trace(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent skill selection audit trail (newest first)."""
    entries = skill_selector.get_trace(limit=min(limit, 200))
    return [
        {
            "timestamp": e.timestamp.isoformat(),
            "task_snippet": e.task_snippet,
            "phase": e.phase,
            "risk": e.risk,
            "skill_name": e.skill_name,
            "confidence": e.confidence,
            "reason": e.reason,
        }
        for e in entries
    ]


@router.get("/{name}/detail", response_model=SkillDetail)
async def get_skill_detail(name: str) -> dict[str, Any]:
    """Return detailed info for a specific skill without colliding with named endpoints."""
    return _skill_detail_response(name)


@router.get("/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> dict[str, Any]:
    """Return detailed info for a specific skill."""
    return _skill_detail_response(name)


@router.post("/{name}/execute", response_model=SkillExecuteResponse)
async def execute_skill(name: str, body: SkillExecuteRequest) -> dict[str, Any]:
    """Execute a skill by injecting its instructions into a conversation turn.

    Reads the SKILL.md, builds a context-enriched prompt, and triggers
    a conversation turn on the session with the skill's instructions.
    """
    from backend.api.ws import ws_manager
    from backend.core.conversation import run_conversation_turn
    from backend.services.session_store import session_store
    from backend.utils.errors import SessionNotFoundError

    skill = get_skill_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    # Build skill execution prompt from the SKILL.md raw content
    param_str = ""
    if body.params:
        param_str = "\n".join(f"- {k}: {v}" for k, v in body.params.items())
        param_str = f"\n\nParameters:\n{param_str}"

    skill_prompt = (
        f"Execute the '{name}' skill.\n\n"
        f"## Skill Instructions\n{skill.raw}\n"
        f"{param_str}"
    )

    if not body.session_id:
        # No session — return the prompt for the caller to use
        return {
            "success": True,
            "message": f"Skill '{name}' prompt generated (no session to execute on).",
            "result": {"prompt": skill_prompt, "skill": name},
        }

    # Execute on the session
    try:
        session = session_store.get(body.session_id)
    except SessionNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Session not found: {body.session_id}") from err

    async def send_to_ui(msg: dict[str, Any]) -> None:
        await ws_manager.send_to_session(body.session_id, msg)  # type: ignore

    try:
        await run_conversation_turn(session, skill_prompt, send_to_ui)
    except Exception as exc:
        logger.error("Skill '%s' execution failed: %s", name, exc)
        return {
            "success": False,
            "message": f"Skill '{name}' execution failed: {exc}",
            "result": None,
        }

    return {
        "success": True,
        "message": f"Skill '{name}' executed successfully.",
        "result": {"skill": name, "session_id": body.session_id},
    }
