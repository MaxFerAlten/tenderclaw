/**
 * HUD (Head-Up Display) — Floating overlay showing real-time agent activity.
 * Inspired by OpenClaw's Live Canvas and Claude Code's background tracking.
 */

import { useSessionStore } from "../../stores/sessionStore";
import { 
  Activity, 
  Terminal, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  ChevronRight
} from "lucide-react";

export function HUD() {
  const activeTools = useSessionStore((s) => s.activeTools);
  const status = useSessionStore((s) => s.status);
  const activeAgent = useSessionStore((s) => s.activeAgent);
  
  const toolList = Array.from(activeTools.values()).slice(-5).reverse();

  if (toolList.length === 0 && status === "idle") return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
      {/* Agent Activity Status */}
      <div className="bg-zinc-900/80 backdrop-blur-md border border-zinc-700/50 rounded-2xl shadow-2xl p-4 min-w-72 flex flex-col gap-3 transform transition-all duration-300 animate-in fade-in slide-in-from-right-4 pointer-events-auto">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${status === "busy" ? "text-amber-400 animate-pulse" : "text-emerald-400"}`} />
            <div className="flex flex-col">
              <span className="text-xs font-bold text-zinc-100 uppercase tracking-tighter">
                {activeAgent} tracing
              </span>
              <span className="text-[9px] text-zinc-500 font-medium -mt-1 tracking-tight">
                Execution active
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 bg-zinc-800/50 rounded-full px-2 py-0.5 border border-zinc-700/30">
            <div className={`w-1.5 h-1.5 rounded-full ${status === "busy" ? "bg-amber-500 animate-ping" : "bg-emerald-500"}`} />
            <span className="text-[10px] font-mono text-zinc-400 uppercase">
              {status}
            </span>
          </div>
        </div>

        {/* Tool Execution List */}
        <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-2 scrollbar-hide">
          {toolList.map((tool) => (
            <div 
              key={tool.tool_use_id} 
              className="group flex flex-col gap-1.5 bg-zinc-950/40 border border-zinc-800/50 rounded-xl p-2.5 transition-all hover:bg-zinc-800/40"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg ${
                    tool.status === "running" ? "bg-amber-500/10 text-amber-500" :
                    tool.status === "error" ? "bg-rose-500/10 text-rose-500" :
                    "bg-emerald-500/10 text-emerald-500"
                  }`}>
                    {tool.status === "running" ? <Loader2 className="w-3 h-3 animate-spin" /> :
                     tool.status === "error" ? <AlertCircle className="w-3 h-3" /> :
                     <CheckCircle2 className="w-3 h-3" />}
                  </div>
                  <span className="text-xs font-mono font-medium text-zinc-200">
                    {tool.tool_name}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-zinc-600 group-hover:text-zinc-400 transition-colors">
                  {tool.tool_use_id.slice(-4)}
                </span>
              </div>

              {tool.status === "completed" && tool.result && (
                <div className="flex items-center gap-1.5 border-t border-zinc-800/30 mt-1 pt-1.5">
                  <Terminal className="w-3 h-3 text-zinc-500" />
                  <p className="text-[10px] text-zinc-500 truncate italic">
                    {tool.result.slice(0, 40)}...
                  </p>
                </div>
              )}
            </div>
          ))}
          
          {toolList.length === 0 && (
            <div className="py-4 text-center">
              <p className="text-xs text-zinc-600 font-medium">Listening for commands...</p>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between mt-1 px-1">
          <div className="flex gap-2">
            <div className="h-1 w-8 rounded-full bg-emerald-500/20"><div className="h-full w-2/3 bg-emerald-500 rounded-full" /></div>
            <div className="h-1 w-8 rounded-full bg-blue-500/20"><div className="h-full w-1/2 bg-blue-500 rounded-full" /></div>
          </div>
          <ChevronRight className="w-3 h-3 text-zinc-700" />
        </div>
      </div>
    </div>
  );
}
