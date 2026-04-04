"""Tools listing endpoint — GET /api/tools."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.tools import ToolSpec
from backend.tools.registry import tool_registry

router = APIRouter()


@router.get("", response_model=list[ToolSpec])
async def list_tools() -> list[ToolSpec]:
    """Return all registered tools with their specs."""
    return tool_registry.list_tools()
