"""Mode state API endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mode", tags=["mode"])


class ModeStatus(BaseModel):
    mode: Literal["idle", "ralph", "team", "analyze", "plan", "tdd", "cancel"]
    active: bool


@router.get("")
async def get_current_mode() -> ModeStatus:
    """Get the current active mode."""
    from backend.core.modes import ModeManager

    mode = ModeManager.get_current()
    return ModeStatus(mode=mode.mode, active=mode.active)


@router.post("/{mode_name}")
async def set_mode(mode_name: str) -> dict:
    """Set the active mode."""
    from backend.core.modes import ModeManager

    valid_modes = ["idle", "ralph", "team", "analyze", "plan", "tdd", "cancel"]
    if mode_name not in valid_modes:
        return {"status": "error", "message": f"Invalid mode: {mode_name}"}

    ModeManager.set_mode(mode_name)
    return {"status": "set", "mode": mode_name}


@router.post("/clear")
async def clear_mode() -> dict:
    """Clear the current mode."""
    from backend.core.modes import ModeManager

    ModeManager.clear_mode()
    return {"status": "cleared"}
