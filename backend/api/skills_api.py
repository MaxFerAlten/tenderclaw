"""Skills API — REST endpoints for skill discovery and execution."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from backend.core.skills import list_available_skills, get_skill_by_name

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


@router.get("", response_model=list[SkillInfo])
async def list_skills() -> list[dict[str, Any]]:
    """Return all available skills."""
    return list_available_skills()


@router.get("/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> dict[str, Any]:
    """Return detailed info for a specific skill."""
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
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {body.session_id}")

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
