/**
 * Sidebar — session list, agent status, and navigation.
 */

import { Link } from "react-router-dom";
import { Settings, ChevronRight } from "lucide-react";
import { useSessionStore } from "../../stores/sessionStore";

export function Sidebar() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const model = useSessionStore((s) => s.model);

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-zinc-800">
        <h1 className="text-lg font-bold text-violet-400 tracking-tight">
          TenderClaw
        </h1>
        <p className="text-xs text-zinc-500 mt-1">Multi-agent AI Assistant</p>
      </div>

      {/* Active Session */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">
          Sessions
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

      {/* Settings Link */}
      <div className="px-3 py-2 border-t border-zinc-800">
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
  );
}
