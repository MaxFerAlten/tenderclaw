/**
 * Sidebar — session list, agent status, and navigation.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Settings, ChevronRight, Bot, Zap, Clock, PanelLeftClose, Network, Plus } from "lucide-react";
import { useSessionStore } from "../../stores/sessionStore";
import { SkillsMenu } from "../skills/SkillsMenu";
import { ws } from "../../api/ws";

interface SidebarProps {
  onToggleSidebar?: () => void;
}

export function Sidebar({ onToggleSidebar }: SidebarProps) {
  const sessionId = useSessionStore((s) => s.sessionId);
  const model = useSessionStore((s) => s.model);
  const reset = useSessionStore((s) => s.reset);
  const [skillsMenuOpen, setSkillsMenuOpen] = useState(false);

  const handleNewChat = () => {
    ws.disconnect();
    reset();
  };

  return (
    <>
      <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-zinc-800 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-violet-400 tracking-tight">
              TenderClaw
            </h1>
            <p className="text-xs text-zinc-500 mt-1">Multi-agent AI Assistant</p>
          </div>
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
              title="Toggle sidebar (Ctrl+B)"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Active Session */}
        <div className="flex-1 overflow-y-auto p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-zinc-500 uppercase tracking-wider">Sessions</div>
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1 px-2 py-1 rounded-md bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition-colors"
              title="New Chat"
            >
              <Plus className="w-3 h-3" />
              New
            </button>
          </div>
          {sessionId ? (
            <div className="rounded-lg bg-zinc-900 p-3 border border-zinc-800">
              <div className="text-sm font-medium text-zinc-200 truncate">
                {sessionId}
              </div>
              <div className="text-xs text-zinc-500 mt-1">{model}</div>
            </div>
          ) : (
            <div className="text-sm text-zinc-600 italic">No active session</div>
          )}
        </div>

        {/* Navigation */}
        <div className="px-3 py-2 border-t border-zinc-800 space-y-1">
          <Link
            to="/history"
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Clock className="w-4 h-4" />
            <span className="text-sm">History</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </Link>
          <button
            onClick={() => setSkillsMenuOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Zap className="w-4 h-4" />
            <span className="text-sm">Skills</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </button>
          <Link
            to="/agents"
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Bot className="w-4 h-4" />
            <span className="text-sm">Agents</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </Link>
          <Link
            to="/coordinator"
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Network className="w-4 h-4" />
            <span className="text-sm">Coordinator</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm">Settings</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </Link>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-zinc-800">
          <div className="text-xs text-zinc-600">v0.1.0 — Phase 5</div>
        </div>
      </aside>

      <SkillsMenu isOpen={skillsMenuOpen} onClose={() => setSkillsMenuOpen(false)} />
    </>
  );
}
