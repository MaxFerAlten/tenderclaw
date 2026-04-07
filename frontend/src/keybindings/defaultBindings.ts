/** Default keyboard shortcuts for TenderClaw. */

import type { KeybindingContextName } from "./types";

export interface DefaultBinding {
  keys: string;
  action: string;
  context: KeybindingContextName;
  description: string;
}

export const DEFAULT_BINDINGS: DefaultBinding[] = [
  // Global
  { keys: "escape", action: "global:cancel", context: "Global", description: "Cancel current action" },
  { keys: "ctrl+shift+p", action: "global:command-palette", context: "Global", description: "Open command palette" },
  { keys: "ctrl+/", action: "global:help", context: "Global", description: "Show keyboard shortcuts" },
  { keys: "ctrl+b", action: "global:toggle-sidebar", context: "Global", description: "Toggle sidebar" },
  { keys: "ctrl+k", action: "global:quick-search", context: "Global", description: "Quick search" },
  
  // Chat
  { keys: "enter", action: "chat:submit", context: "Chat", description: "Submit message" },
  { keys: "shift+enter", action: "chat:newline", context: "Chat", description: "Insert newline" },
  { keys: "ctrl+enter", action: "chat:submit-multiline", context: "Chat", description: "Submit multiline" },
  { keys: "ctrl+up", action: "chat:history-up", context: "Chat", description: "Previous command" },
  { keys: "ctrl+down", action: "chat:history-down", context: "Chat", description: "Next command" },
  { keys: "ctrl+l", action: "chat:clear", context: "Chat", description: "Clear chat" },
  
  // Settings
  { keys: "escape", action: "settings:close", context: "Settings", description: "Close settings" },
  { keys: "tab", action: "settings:tab-next", context: "Settings", description: "Next tab" },
  { keys: "shift+tab", action: "settings:tab-prev", context: "Settings", description: "Previous tab" },
  
  // History
  { keys: "escape", action: "history:close", context: "HistorySearch", description: "Close history" },
  { keys: "enter", action: "history:select", context: "HistorySearch", description: "Select session" },
  { keys: "ctrl+f", action: "history:search", context: "HistorySearch", description: "Focus search" },
  { keys: "j", action: "history:next", context: "HistorySearch", description: "Next item" },
  { keys: "k", action: "history:prev", context: "HistorySearch", description: "Previous item" },
  
  // Agent Editor
  { keys: "ctrl+s", action: "agents:save", context: "AgentEditor", description: "Save agent" },
  { keys: "ctrl+n", action: "agents:new", context: "AgentEditor", description: "New agent" },
  { keys: "ctrl+d", action: "agents:duplicate", context: "AgentEditor", description: "Duplicate agent" },
  { keys: "delete", action: "agents:delete", context: "AgentEditor", description: "Delete agent" },
  { keys: "escape", action: "agents:cancel", context: "AgentEditor", description: "Cancel editing" },
  
  // Canvas
  { keys: "ctrl+=", action: "canvas:zoom-in", context: "Canvas", description: "Zoom in" },
  { keys: "ctrl+-", action: "canvas:zoom-out", context: "Canvas", description: "Zoom out" },
  { keys: "ctrl+0", action: "canvas:reset-zoom", context: "Canvas", description: "Reset zoom" },
  { keys: "f", action: "canvas:fit", context: "Canvas", description: "Fit to view" },
  
  // Skills Menu
  { keys: "escape", action: "skills:close", context: "SkillsMenu", description: "Close skills menu" },
  { keys: "enter", action: "skills:execute", context: "SkillsMenu", description: "Execute selected skill" },
  { keys: "j", action: "skills:next", context: "SkillsMenu", description: "Next skill" },
  { keys: "k", action: "skills:prev", context: "SkillsMenu", description: "Previous skill" },
  { keys: "/", action: "skills:search", context: "SkillsMenu", description: "Focus search" },
];

export const ALL_ACTIONS: Array<{ action: string; description: string; category: string }> = [
  // Global actions
  { action: "global:cancel", description: "Cancel current action", category: "Global" },
  { action: "global:command-palette", description: "Open command palette", category: "Global" },
  { action: "global:help", description: "Show keyboard shortcuts", category: "Global" },
  { action: "global:toggle-sidebar", description: "Toggle sidebar", category: "Global" },
  { action: "global:quick-search", description: "Quick search", category: "Global" },
  
  // Chat actions
  { action: "chat:submit", description: "Submit message", category: "Chat" },
  { action: "chat:newline", description: "Insert newline", category: "Chat" },
  { action: "chat:submit-multiline", description: "Submit multiline", category: "Chat" },
  { action: "chat:history-up", description: "Previous command", category: "Chat" },
  { action: "chat:history-down", description: "Next command", category: "Chat" },
  { action: "chat:clear", description: "Clear chat", category: "Chat" },
  
  // Settings actions
  { action: "settings:close", description: "Close settings", category: "Settings" },
  { action: "settings:tab-next", description: "Next tab", category: "Settings" },
  { action: "settings:tab-prev", description: "Previous tab", category: "Settings" },
  
  // History actions
  { action: "history:close", description: "Close history", category: "History" },
  { action: "history:select", description: "Select session", category: "History" },
  { action: "history:search", description: "Focus search", category: "History" },
  { action: "history:next", description: "Next item", category: "History" },
  { action: "history:prev", description: "Previous item", category: "History" },
  
  // Agent actions
  { action: "agents:save", description: "Save agent", category: "Agents" },
  { action: "agents:new", description: "New agent", category: "Agents" },
  { action: "agents:duplicate", description: "Duplicate agent", category: "Agents" },
  { action: "agents:delete", description: "Delete agent", category: "Agents" },
  { action: "agents:cancel", description: "Cancel editing", category: "Agents" },
  
  // Canvas actions
  { action: "canvas:zoom-in", description: "Zoom in", category: "Canvas" },
  { action: "canvas:zoom-out", description: "Zoom out", category: "Canvas" },
  { action: "canvas:reset-zoom", description: "Reset zoom", category: "Canvas" },
  { action: "canvas:fit", description: "Fit to view", category: "Canvas" },
  
  // Skills actions
  { action: "skills:close", description: "Close skills menu", category: "Skills" },
  { action: "skills:execute", description: "Execute selected skill", category: "Skills" },
  { action: "skills:next", description: "Next skill", category: "Skills" },
  { action: "skills:prev", description: "Previous skill", category: "Skills" },
  { action: "skills:search", description: "Focus search", category: "Skills" },
];
