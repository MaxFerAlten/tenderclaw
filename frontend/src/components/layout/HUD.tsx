/**
 * HUD (Head-Up Display) — Floating overlay showing real-time agent activity.
 *
 * Features:
 * - Pipeline stage tracker (Oracle → Metis → Sisyphus → Momus → Fixer → Sentinel)
 * - Active tool execution list with status badges
 * - Turn counter and elapsed time
 * - Thinking indicator with phase visualization
 * - Notification bell with unread count
 * - Tool progress streaming
 * - Collapsible design with smooth animations
 */

import { useState, useEffect } from "react";
import { useSessionStore } from "../../stores/sessionStore";
import { useNotificationStore } from "../../stores/notificationStore";
import type { PipelineStageState } from "../../stores/sessionStore";
import {
  Activity,
  Terminal,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Clock,
  Zap,
  Search,
  FileText,
  Hammer,
  Eye,
  Wrench,
  Shield,
  Bell,
  Brain,
  BrainCircuit,
} from "lucide-react";

const STAGE_META: Record<string, { label: string; icon: typeof Search }> = {
  oracle:   { label: "Research",  icon: Search },
  metis:    { label: "Plan",      icon: FileText },
  sisyphus: { label: "Execute",   icon: Hammer },
  momus:    { label: "Verify",    icon: Eye },
  fixer:    { label: "Fix",       icon: Wrench },
  sentinel: { label: "Security",  icon: Shield },
};

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function StageIcon({ stage, status }: { stage: string; status: string }) {
  const meta = STAGE_META[stage];
  const Icon = meta?.icon ?? Zap;

  if (status === "started") {
    return (
      <div className="p-1 rounded-md bg-amber-500/15">
        <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
      </div>
    );
  }
  if (status === "completed") {
    return (
      <div className="p-1 rounded-md bg-emerald-500/15">
        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="p-1 rounded-md bg-rose-500/15">
        <AlertCircle className="w-3 h-3 text-rose-400" />
      </div>
    );
  }
  return (
    <div className="p-1 rounded-md bg-zinc-800/50">
      <Icon className="w-3 h-3 text-zinc-600" />
    </div>
  );
}

function PipelineTracker({ stages }: { stages: PipelineStageState[] }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-widest mb-0.5">
        Pipeline
      </span>
      <div className="flex items-center gap-1">
        {stages.map((s, i) => {
          const meta = STAGE_META[s.stage];
          const barColor =
            s.status === "completed" ? "bg-emerald-500" :
            s.status === "started"   ? "bg-amber-500 animate-pulse" :
            s.status === "failed"    ? "bg-rose-500" :
            "bg-zinc-700";

          return (
            <div key={s.stage} className="flex items-center gap-1 flex-1">
              <div className="flex flex-col items-center gap-0.5 flex-1">
                <StageIcon stage={s.stage} status={s.status} />
                <span className="text-[8px] text-zinc-500 font-medium">
                  {meta?.label ?? s.stage}
                </span>
                <div className={`h-0.5 w-full rounded-full ${barColor}`} />
              </div>
              {i < stages.length - 1 && (
                <div className="w-2 h-px bg-zinc-700 mt-[-8px]" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ThinkingIndicator({ agentName, phase, progressPct, detail }: {
  agentName: string;
  phase: string;
  progressPct: number;
  detail: string;
}) {
  const phaseLabel: Record<string, string> = {
    analyzing: "Analyzing",
    planning: "Planning",
    reasoning: "Reasoning",
    synthesizing: "Synthesizing",
  };

  return (
    <div className="flex flex-col gap-1.5 border-t border-zinc-800/50 pt-2">
      <div className="flex items-center gap-2">
        <BrainCircuit className="w-3.5 h-3.5 text-violet-400 animate-pulse" />
        <span className="text-[10px] font-medium text-violet-300 uppercase tracking-wide">
          {phaseLabel[phase] ?? phase}
        </span>
        <span className="text-[9px] text-zinc-500 ml-auto">
          {agentName}
        </span>
      </div>

      {progressPct > 0 && (
        <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.min(progressPct, 100)}%` }}
          />
        </div>
      )}

      {detail && (
        <p className="text-[9px] text-zinc-500 italic truncate">{detail}</p>
      )}
    </div>
  );
}

export function HUD() {
  const activeTools = useSessionStore((s) => s.activeTools);
  const status = useSessionStore((s) => s.status);
  const activeAgent = useSessionStore((s) => s.activeAgent);
  const pipelineActive = useSessionStore((s) => s.pipelineActive);
  const pipelineStages = useSessionStore((s) => s.pipelineStages);
  const turnCount = useSessionStore((s) => s.turnCount);
  const turnStartedAt = useSessionStore((s) => s.turnStartedAt);

  const thinking = useNotificationStore((s) => s.thinking);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const togglePanel = useNotificationStore((s) => s.togglePanel);

  const [collapsed, setCollapsed] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const toolList = Array.from(activeTools.values()).slice(-5).reverse();
  const hasActivity = toolList.length > 0 || status === "busy" || pipelineActive;

  useEffect(() => {
    if (status !== "busy" || !turnStartedAt) {
      setElapsed(0);
      return;
    }
    setElapsed(Date.now() - turnStartedAt);
    const timer = setInterval(() => {
      setElapsed(Date.now() - (turnStartedAt ?? Date.now()));
    }, 1000);
    return () => clearInterval(timer);
  }, [status, turnStartedAt]);

  if (!hasActivity) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
      <div className="bg-zinc-900/85 backdrop-blur-lg border border-zinc-700/50 rounded-2xl shadow-2xl min-w-80 max-w-96 flex flex-col transform transition-all duration-300 animate-in fade-in slide-in-from-right-4 pointer-events-auto">
        {/* Header — always visible */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-between p-3 pb-2 w-full text-left hover:bg-zinc-800/30 rounded-t-2xl transition-colors"
        >
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${status === "busy" ? "text-amber-400 animate-pulse" : "text-emerald-400"}`} />
            <div className="flex flex-col">
              <span className="text-xs font-bold text-zinc-100 uppercase tracking-tight">
                {activeAgent}
              </span>
              <span className="text-[9px] text-zinc-500 font-medium -mt-0.5">
                {status === "busy" ? "Working..." : "Idle"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Notification bell */}
            <button
              onClick={(e) => { e.stopPropagation(); togglePanel(); }}
              className="relative p-1 rounded-lg hover:bg-zinc-800/50 transition-colors"
            >
              <Bell className="w-3.5 h-3.5 text-zinc-400" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-rose-500 rounded-full text-[8px] font-bold text-white flex items-center justify-center animate-bounce">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {/* Thinking indicator (compact) */}
            {thinking?.active && (
              <div className="flex items-center gap-1 bg-violet-500/10 border border-violet-500/20 rounded-full px-2 py-0.5">
                <Brain className="w-2.5 h-2.5 text-violet-400 animate-pulse" />
                <span className="text-[10px] font-mono text-violet-300">
                  {thinking.phase}
                </span>
              </div>
            )}

            {/* Turn counter */}
            {turnCount > 0 && (
              <div className="flex items-center gap-1 bg-zinc-800/50 rounded-full px-2 py-0.5 border border-zinc-700/30">
                <Zap className="w-2.5 h-2.5 text-violet-400" />
                <span className="text-[10px] font-mono text-zinc-400">
                  T{turnCount}
                </span>
              </div>
            )}
            {/* Elapsed time */}
            {status === "busy" && elapsed > 0 && (
              <div className="flex items-center gap-1 bg-zinc-800/50 rounded-full px-2 py-0.5 border border-zinc-700/30">
                <Clock className="w-2.5 h-2.5 text-zinc-500" />
                <span className="text-[10px] font-mono text-zinc-400">
                  {formatElapsed(elapsed)}
                </span>
              </div>
            )}
            {/* Status dot */}
            <div className="flex items-center gap-1 bg-zinc-800/50 rounded-full px-2 py-0.5 border border-zinc-700/30">
              <div className={`w-1.5 h-1.5 rounded-full ${status === "busy" ? "bg-amber-500 animate-ping" : "bg-emerald-500"}`} />
              <span className="text-[10px] font-mono text-zinc-400 uppercase">
                {status}
              </span>
            </div>
            {collapsed ? (
              <ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            )}
          </div>
        </button>

        {/* Collapsible body */}
        {!collapsed && (
          <div className="flex flex-col gap-3 px-3 pb-3">
            {/* Thinking progress (expanded) */}
            {thinking?.active && (
              <ThinkingIndicator
                agentName={thinking.agentName}
                phase={thinking.phase}
                progressPct={thinking.progressPct}
                detail={thinking.detail}
              />
            )}

            {/* Pipeline Stages */}
            {pipelineActive && pipelineStages.length > 0 && (
              <div className="border-t border-zinc-800/50 pt-2">
                <PipelineTracker stages={pipelineStages} />
              </div>
            )}

            {/* Tool Execution List */}
            {toolList.length > 0 && (
              <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto scrollbar-hide">
                {toolList.map((tool) => (
                  <div
                    key={tool.tool_use_id}
                    className="group flex flex-col gap-1 bg-zinc-950/40 border border-zinc-800/50 rounded-xl p-2 transition-all hover:bg-zinc-800/40"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`p-1 rounded-lg ${
                          tool.status === "running" ? "bg-amber-500/10 text-amber-500" :
                          tool.status === "error" ? "bg-rose-500/10 text-rose-500" :
                          "bg-emerald-500/10 text-emerald-500"
                        }`}>
                          {tool.status === "running" ? <Loader2 className="w-3 h-3 animate-spin" /> :
                           tool.status === "error" ? <AlertCircle className="w-3 h-3" /> :
                           <CheckCircle2 className="w-3 h-3" />}
                        </div>
                        <span className="text-xs font-mono font-medium text-zinc-200 truncate max-w-40">
                          {tool.tool_name}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-zinc-600 group-hover:text-zinc-400 transition-colors">
                        {tool.tool_use_id.slice(-4)}
                      </span>
                    </div>

                    {tool.status === "completed" && tool.result && (
                      <div className="flex items-center gap-1.5 border-t border-zinc-800/30 mt-0.5 pt-1">
                        <Terminal className="w-3 h-3 text-zinc-500 shrink-0" />
                        <p className="text-[10px] text-zinc-500 truncate italic">
                          {tool.result.slice(0, 60)}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {toolList.length === 0 && !pipelineActive && !thinking?.active && (
              <div className="py-3 text-center border-t border-zinc-800/50">
                <p className="text-xs text-zinc-600 font-medium">Listening for commands...</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
