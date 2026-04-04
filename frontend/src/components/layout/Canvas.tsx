/**
 * Canvas Component — A2UI (Agent-to-UI) panel for persistent artifacts.
 * Inspired by Claude's Artifacts and OpenClaw's Live Canvas.
 */

import { useSessionStore } from "../../stores/sessionStore";
import { X, Code, FileText, Download } from "lucide-react";

export function Canvas() {
  const artifacts = useSessionStore((s) => s.artifacts);
  const activeArtifactId = useSessionStore((s) => s.activeArtifactId);
  const set = useSessionStore.setState;

  if (!activeArtifactId) return null;

  const artifact = artifacts.get(activeArtifactId);
  if (!artifact) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-[500px] bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-40 animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          {artifact.language ? (
            <Code className="w-5 h-5 text-blue-400" />
          ) : (
            <FileText className="w-5 h-5 text-emerald-400" />
          )}
          <h2 className="text-sm font-semibold text-zinc-100 truncate max-w-64">
            {artifact.title}
          </h2>
        </div>
        <div className="flex items-center gap-2">
           <button className="p-1 px-2 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors">
            <Download className="w-4 h-4" />
          </button>
          <button 
            onClick={() => set({ activeArtifactId: null })}
            className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto p-6 font-mono text-xs leading-relaxed text-zinc-300 bg-zinc-950">
        <pre className="whitespace-pre-wrap break-all">
          {artifact.content}
        </pre>
      </div>

      {/* Footer / Status */}
      <div className="p-2 px-4 bg-zinc-900 border-t border-zinc-800 flex items-center justify-between">
        <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold">
          Artifact ID: {artifact.artifact_id}
        </span>
        {artifact.language && (
          <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20">
            {artifact.language}
          </span>
        )}
      </div>
    </div>
  );
}
