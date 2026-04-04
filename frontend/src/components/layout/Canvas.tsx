/**
 * Canvas Component — A2UI (Agent-to-UI) panel for persistent artifacts.
 * Inspired by Claude's Artifacts and OpenClaw's Live Canvas.
 * 
 * Features:
 * - Artifact list sidebar
 * - Full-screen preview
 * - Code highlighting
 * - Export options
 * - Artifact creation
 */

import { useState, useCallback } from "react";
import { useSessionStore } from "../../stores/sessionStore";
import { 
  X, Code, FileText, Download, ChevronRight, 
  PanelRightClose, PanelRight, Eye, Edit3, Trash2 
} from "lucide-react";
import { CodeBlock } from "../shared/CodeBlock";

export function Canvas() {
  const artifacts = useSessionStore((s) => s.artifacts);
  const activeArtifactId = useSessionStore((s) => s.activeArtifactId);
  const set = useSessionStore.setState;
  
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<"preview" | "code">("preview");

  const artifact = activeArtifactId ? artifacts.get(activeArtifactId) : null;
  const artifactList = Array.from(artifacts.values());

  const handleClose = useCallback(() => {
    set({ activeArtifactId: null });
  }, [set]);

  const handleSelect = useCallback((id: string) => {
    set({ activeArtifactId: id });
  }, [set]);

  const handleExport = useCallback(() => {
    if (!artifact) return;
    
    const blob = new Blob([artifact.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.title || `artifact-${artifact.artifact_id}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [artifact]);

  // Collapsed state - show only toggle button
  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="fixed right-0 top-20 z-50 bg-zinc-800 border border-zinc-700 rounded-l-lg px-2 py-4 hover:bg-zinc-700 transition-colors"
        title="Open Canvas"
      >
        <PanelRight className="w-5 h-5 text-zinc-400" />
      </button>
    );
  }

  // No artifacts state
  if (artifacts.size === 0) {
    return (
      <div className="fixed inset-y-0 right-0 w-16 bg-zinc-900 border-l border-zinc-800 flex flex-col items-center py-4 z-40">
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-2 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors"
          title="Collapse Canvas"
        >
          <PanelRightClose className="w-5 h-5" />
        </button>
        <div className="mt-4 text-zinc-600 text-xs text-center writing-mode-vertical" style={{ writingMode: "vertical-rl" }}>
          No artifacts
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-y-0 right-0 w-[600px] bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-40 animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors"
            title="Collapse"
          >
            <PanelRightClose className="w-4 h-4" />
          </button>
          <span className="text-sm font-semibold text-zinc-200">Canvas</span>
          <span className="text-xs bg-zinc-700 text-zinc-400 px-2 py-0.5 rounded-full">
            {artifacts.size}
          </span>
        </div>
        
        {artifact && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setViewMode("preview")}
              className={`p-1.5 rounded-md transition-colors ${viewMode === "preview" ? "bg-blue-500/20 text-blue-400" : "hover:bg-zinc-800 text-zinc-400"}`}
              title="Preview"
            >
              <Eye className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("code")}
              className={`p-1.5 rounded-md transition-colors ${viewMode === "code" ? "bg-blue-500/20 text-blue-400" : "hover:bg-zinc-800 text-zinc-400"}`}
              title="Code"
            >
              <Code className="w-4 h-4" />
            </button>
            <button
              onClick={handleExport}
              className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors"
              title="Export"
            >
              <Download className="w-4 h-4" />
            </button>
            <button
              onClick={handleClose}
              className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Artifact List */}
        <div className="w-48 border-r border-zinc-800 bg-zinc-950/50 overflow-y-auto">
          <div className="p-2 space-y-1">
            {artifactList.map((a) => (
              <button
                key={a.artifact_id}
                onClick={() => handleSelect(a.artifact_id)}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors flex items-center gap-2 ${
                  activeArtifactId === a.artifact_id 
                    ? "bg-blue-500/20 text-blue-300" 
                    : "hover:bg-zinc-800 text-zinc-400"
                }`}
              >
                {a.language ? (
                  <Code className="w-4 h-4 shrink-0" />
                ) : (
                  <FileText className="w-4 h-4 shrink-0" />
                )}
                <span className="text-xs truncate">{a.title || "Untitled"}</span>
                <ChevronRight className="w-3 h-3 shrink-0 ml-auto" />
              </button>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {artifact ? (
            <>
              {/* Artifact Header */}
              <div className="p-3 border-b border-zinc-800 flex items-center gap-3">
                {artifact.language ? (
                  <Code className="w-5 h-5 text-blue-400" />
                ) : (
                  <FileText className="w-5 h-5 text-emerald-400" />
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-zinc-100 truncate">
                    {artifact.title}
                  </h3>
                  <p className="text-[10px] text-zinc-500">
                    ID: {artifact.artifact_id}
                  </p>
                </div>
                {artifact.language && (
                  <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20">
                    {artifact.language}
                  </span>
                )}
              </div>

              {/* Content Area */}
              <div className="flex-1 overflow-auto bg-zinc-950">
                {viewMode === "code" ? (
                  <CodeBlock
                    code={artifact.content}
                    language={artifact.language}
                  />
                ) : (
                  <pre className="p-4 font-mono text-xs leading-relaxed text-zinc-300 whitespace-pre-wrap break-all">
                    {artifact.content}
                  </pre>
                )}
              </div>

              {/* Footer */}
              <div className="p-2 px-4 bg-zinc-900 border-t border-zinc-800 flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">
                  {(artifact.content.length / 1024).toFixed(1)} KB
                </span>
                <div className="flex items-center gap-2">
                  <button 
                    className="p-1 rounded hover:bg-zinc-800 text-zinc-500 transition-colors"
                    title="Edit"
                  >
                    <Edit3 className="w-3 h-3" />
                  </button>
                  <button 
                    className="p-1 rounded hover:bg-zinc-800 text-zinc-500 transition-colors"
                    title="Delete"
                    onClick={() => {
                      const newArtifacts = new Map(artifacts);
                      newArtifacts.delete(artifact.artifact_id);
                      set({ artifacts: newArtifacts, activeArtifactId: null });
                    }}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-zinc-500">
              <p className="text-sm">Select an artifact to view</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
