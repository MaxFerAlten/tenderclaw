"""Skills API — REST endpoints for skill discovery and execution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from backend.core.skills import list_available_skills, get_skill_by_name

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
    """Execute a skill (placeholder — actual execution depends on skill type)."""
    skill = get_skill_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {
        "success": True,
        "message": f"Skill '{name}' is ready to execute.",
        "result": {
            "skill": name,
            "trigger": skill.trigger,
            "session_id": body.session_id,
            "params": body.params,
        },
    }
