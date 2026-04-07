"""API endpoints for keybindings management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/keybindings", tags=["keybindings"])

class DefaultBinding(BaseModel):
    keys: str
    action: str
    context: str
    description: str

class UserBinding(BaseModel):
    action: str
    keys: str

class BindingStatus(BaseModel):
    total: int
    user_bindings: int

DEFAULT_BINDINGS = [
    {"keys": "escape", "action": "global:cancel", "context": "Global", "description": "Cancel current action"},
    {"keys": "ctrl+shift+p", "action": "global:command-palette", "context": "Global", "description": "Open command palette"},
    {"keys": "ctrl+/", "action": "global:help", "context": "Global", "description": "Show keyboard shortcuts"},
    {"keys": "ctrl+b", "action": "global:toggle-sidebar", "context": "Global", "description": "Toggle sidebar"},
    {"keys": "ctrl+k", "action": "global:quick-search", "context": "Global", "description": "Quick search"},
    {"keys": "enter", "action": "chat:submit", "context": "Chat", "description": "Submit message"},
    {"keys": "shift+enter", "action": "chat:newline", "context": "Chat", "description": "Insert newline"},
    {"keys": "ctrl+enter", "action": "chat:submit-multiline", "context": "Chat", "description": "Submit multiline"},
    {"keys": "ctrl+up", "action": "chat:history-up", "context": "Chat", "description": "Previous command"},
    {"keys": "ctrl+down", "action": "chat:history-down", "context": "Chat", "description": "Next command"},
    {"keys": "ctrl+l", "action": "chat:clear", "context": "Chat", "description": "Clear chat"},
    {"keys": "escape", "action": "settings:close", "context": "Settings", "description": "Close settings"},
    {"keys": "tab", "action": "settings:tab-next", "context": "Settings", "description": "Next tab"},
    {"keys": "shift+tab", "action": "settings:tab-prev", "context": "Settings", "description": "Previous tab"},
    {"keys": "escape", "action": "history:close", "context": "HistorySearch", "description": "Close history"},
    {"keys": "enter", "action": "history:select", "context": "HistorySearch", "description": "Select session"},
    {"keys": "ctrl+f", "action": "history:search", "context": "HistorySearch", "description": "Focus search"},
    {"keys": "j", "action": "history:next", "context": "HistorySearch", "description": "Next item"},
    {"keys": "k", "action": "history:prev", "context": "HistorySearch", "description": "Previous item"},
    {"keys": "ctrl+s", "action": "agents:save", "context": "AgentEditor", "description": "Save agent"},
    {"keys": "ctrl+n", "action": "agents:new", "context": "AgentEditor", "description": "New agent"},
    {"keys": "ctrl+d", "action": "agents:duplicate", "context": "AgentEditor", "description": "Duplicate agent"},
    {"keys": "delete", "action": "agents:delete", "context": "AgentEditor", "description": "Delete agent"},
    {"keys": "escape", "action": "agents:cancel", "context": "AgentEditor", "description": "Cancel editing"},
    {"keys": "ctrl+=", "action": "canvas:zoom-in", "context": "Canvas", "description": "Zoom in"},
    {"keys": "ctrl+-", "action": "canvas:zoom-out", "context": "Canvas", "description": "Zoom out"},
    {"keys": "ctrl+0", "action": "canvas:reset-zoom", "context": "Canvas", "description": "Reset zoom"},
    {"keys": "f", "action": "canvas:fit", "context": "Canvas", "description": "Fit to view"},
    {"keys": "escape", "action": "skills:close", "context": "SkillsMenu", "description": "Close skills menu"},
    {"keys": "enter", "action": "skills:execute", "context": "SkillsMenu", "description": "Execute selected skill"},
    {"keys": "j", "action": "skills:next", "context": "SkillsMenu", "description": "Next skill"},
    {"keys": "k", "action": "skills:prev", "context": "SkillsMenu", "description": "Previous skill"},
    {"keys": "/", "action": "skills:search", "context": "SkillsMenu", "description": "Focus search"},
]

ALL_ACTIONS = [
    {"action": "global:cancel", "description": "Cancel current action", "category": "Global"},
    {"action": "global:command-palette", "description": "Open command palette", "category": "Global"},
    {"action": "global:help", "description": "Show keyboard shortcuts", "category": "Global"},
    {"action": "global:toggle-sidebar", "description": "Toggle sidebar", "category": "Global"},
    {"action": "global:quick-search", "description": "Quick search", "category": "Global"},
    {"action": "chat:submit", "description": "Submit message", "category": "Chat"},
    {"action": "chat:newline", "description": "Insert newline", "category": "Chat"},
    {"action": "chat:submit-multiline", "description": "Submit multiline", "category": "Chat"},
    {"action": "chat:history-up", "description": "Previous command", "category": "Chat"},
    {"action": "chat:history-down", "description": "Next command", "category": "Chat"},
    {"action": "chat:clear", "description": "Clear chat", "category": "Chat"},
    {"action": "settings:close", "description": "Close settings", "category": "Settings"},
    {"action": "settings:tab-next", "description": "Next tab", "category": "Settings"},
    {"action": "settings:tab-prev", "description": "Previous tab", "category": "Settings"},
    {"action": "history:close", "description": "Close history", "category": "History"},
    {"action": "history:select", "description": "Select session", "category": "History"},
    {"action": "history:search", "description": "Focus search", "category": "History"},
    {"action": "history:next", "description": "Next item", "category": "History"},
    {"action": "history:prev", "description": "Previous item", "category": "History"},
    {"action": "agents:save", "description": "Save agent", "category": "Agents"},
    {"action": "agents:new", "description": "New agent", "category": "Agents"},
    {"action": "agents:duplicate", "description": "Duplicate agent", "category": "Agents"},
    {"action": "agents:delete", "description": "Delete agent", "category": "Agents"},
    {"action": "agents:cancel", "description": "Cancel editing", "category": "Agents"},
    {"action": "canvas:zoom-in", "description": "Zoom in", "category": "Canvas"},
    {"action": "canvas:zoom-out", "description": "Zoom out", "category": "Canvas"},
    {"action": "canvas:reset-zoom", "description": "Reset zoom", "category": "Canvas"},
    {"action": "canvas:fit", "description": "Fit to view", "category": "Canvas"},
    {"action": "skills:close", "description": "Close skills menu", "category": "Skills"},
    {"action": "skills:execute", "description": "Execute selected skill", "category": "Skills"},
    {"action": "skills:next", "description": "Next skill", "category": "Skills"},
    {"action": "skills:prev", "description": "Previous skill", "category": "Skills"},
    {"action": "skills:search", "description": "Focus search", "category": "Skills"},
]

@router.get("/defaults")
async def get_default_bindings() -> list[DefaultBinding]:
    """Get all default keybindings."""
    return [
        DefaultBinding(
            keys=b["keys"],
            action=b["action"],
            context=b["context"],
            description=b["description"],
        )
        for b in DEFAULT_BINDINGS
    ]

@router.get("/actions")
async def get_all_actions() -> list[dict[str, str]]:
    """Get all available actions."""
    return ALL_ACTIONS

@router.get("/status")
async def get_binding_status() -> BindingStatus:
    """Get keybinding status."""
    return BindingStatus(total=len(DEFAULT_BINDINGS), user_bindings=0)

@router.get("/user")
async def get_user_bindings() -> list[UserBinding]:
    """Get user custom bindings."""
    return []

@router.put("/user")
async def save_user_bindings(bindings: list[UserBinding]) -> dict[str, Any]:
    """Save user custom bindings."""
    return {"saved": len(bindings)}
