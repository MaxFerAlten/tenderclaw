"""Agents API — CRUD endpoints for agent definitions.

Built-in agents (from register_builtin_agents) are read-only: they can be
retrieved and their enabled/default_model fields can be patched, but they
cannot be deleted.  Custom user-created agents are fully mutable.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.agents.registry import agent_registry
from backend.schemas.agents import AgentDefinition
from backend.services.custom_agent_store import custom_agent_store

logger = logging.getLogger("tenderclaw.api.agents")
router = APIRouter()

# Names of built-in agents — protected from deletion
_BUILTIN_NAMES = {
    "sisyphus", "oracle", "explorer", "metis", "momus", "sentinel",
    "hephaestus", "atlas", "librarian", "scribe", "fixer", "looker",
}


class AgentPatch(BaseModel):
    """Partial update — only fields provided are changed."""
    description: str | None = None
    default_model: str | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None
    enabled: bool | None = None
    max_tokens: int | None = None


# ---------------------------------------------------------------------------
# GET  /api/agents
# ---------------------------------------------------------------------------
@router.get("", response_model=list[dict[str, Any]])
async def list_agents() -> list[dict[str, Any]]:
    """Return all registered agents (built-in + custom)."""
    agents = agent_registry.list_all()
    result = []
    for a in agents:
        d = a.model_dump()
        d["is_builtin"] = a.name.lower() in _BUILTIN_NAMES
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# GET  /api/agents/{name}
# ---------------------------------------------------------------------------
@router.get("/{name}", response_model=dict[str, Any])
async def get_agent(name: str) -> dict[str, Any]:
    """Return a single agent definition."""
    try:
        agent = agent_registry.get(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    d = agent.model_dump()
    d["is_builtin"] = name.lower() in _BUILTIN_NAMES
    return d


# ---------------------------------------------------------------------------
# POST  /api/agents  (create)
# ---------------------------------------------------------------------------
@router.post("", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_agent(agent: AgentDefinition) -> dict[str, Any]:
    """Create a new custom agent."""
    name_lower = agent.name.lower()
    if name_lower in _BUILTIN_NAMES:
        raise HTTPException(
            status_code=409,
            detail=f"'{agent.name}' is a reserved built-in agent name.",
        )
    # Register in memory + persist to disk
    agent_registry.register(agent)
    custom_agent_store.save(agent)
    logger.info("Custom agent created: %s", agent.name)
    d = agent.model_dump()
    d["is_builtin"] = False
    return d


# ---------------------------------------------------------------------------
# PUT  /api/agents/{name}  (full replace for custom agents)
# ---------------------------------------------------------------------------
@router.put("/{name}", response_model=dict[str, Any])
async def update_agent(name: str, agent: AgentDefinition) -> dict[str, Any]:
    """Full update of a custom agent."""
    name_lower = name.lower()
    if name_lower in _BUILTIN_NAMES:
        raise HTTPException(
            status_code=403,
            detail="Built-in agents cannot be fully replaced. Use PATCH instead.",
        )
    if agent.name.lower() != name_lower:
        raise HTTPException(status_code=400, detail="Agent name in body must match URL.")
    agent_registry.register(agent)
    custom_agent_store.save(agent)
    d = agent.model_dump()
    d["is_builtin"] = False
    return d


# ---------------------------------------------------------------------------
# PATCH  /api/agents/{name}  (partial update — built-ins allowed for safe fields)
# ---------------------------------------------------------------------------
@router.patch("/{name}", response_model=dict[str, Any])
async def patch_agent(name: str, patch: AgentPatch) -> dict[str, Any]:
    """Partially update an agent. Built-ins: only enabled/default_model/system_prompt allowed."""
    try:
        existing = agent_registry.get(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    is_builtin = name.lower() in _BUILTIN_NAMES
    updates = patch.model_dump(exclude_none=True)

    if is_builtin:
        # Restrict what can be changed on built-ins
        allowed = {"enabled", "default_model", "system_prompt"}
        forbidden = set(updates.keys()) - allowed
        if forbidden:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot change {forbidden} on built-in agents.",
            )

    updated = existing.model_copy(update=updates)
    agent_registry.register(updated)

    # Custom agents are persisted; built-ins are memory-only patches
    if not is_builtin:
        custom_agent_store.save(updated)

    d = updated.model_dump()
    d["is_builtin"] = is_builtin
    return d


# ---------------------------------------------------------------------------
# DELETE  /api/agents/{name}
# ---------------------------------------------------------------------------
@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(name: str) -> None:
    """Delete a custom agent (built-ins are protected)."""
    name_lower = name.lower()
    if name_lower in _BUILTIN_NAMES:
        raise HTTPException(
            status_code=403,
            detail="Built-in agents cannot be deleted.",
        )
    try:
        agent_registry.get(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Remove from in-memory registry
    agent_registry._agents.pop(name_lower, None)
    custom_agent_store.delete(name_lower)
    logger.info("Custom agent deleted: %s", name)
