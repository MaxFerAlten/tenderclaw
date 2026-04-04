/**
 * ToolUseCard — inline rendering of tool_use and tool_result content blocks.
 */

import { useState } from "react";
import type { ToolUseBlock, ToolResultBlock } from "../../api/types";
import { useSessionStore } from "../../stores/sessionStore";
import { Spinner } from "../shared/Spinner";

interface Props {
  block: ToolUseBlock | ToolResultBlock;
}

export function ToolUseCard({ block }: Props) {
  const [expanded, setExpanded] = useState(false);
  const activeTools = useSessionStore((s) => s.activeTools);

  if (block.type === "tool_use") {
    const toolState = activeTools.get(block.id);
    const status = toolState?.status ?? "running";
    return (
      <div className="my-2 rounded-lg border border-zinc-700 bg-zinc-900/60 text-xs">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-800/50 rounded-lg"
          onClick={() => setExpanded(!expanded)}
        >
          <StatusIcon status={status} />
          <span className="font-mono font-semibold text-violet-400">{block.name}</span>
          <StatusBadge status={status} />
          <span className="ml-auto text-zinc-600">{expanded ? "▲" : "▼"}</span>
        </button>
        {expanded && (
          <pre className="px-3 pb-2 overflow-x-auto text-zinc-400 max-h-48 overflow-y-auto">
            {JSON.stringify(block.input, null, 2)}
          </pre>
        )}
      </div>
    );
  }

  // tool_result
  const isError = block.is_error;
  const content = block.content;
  const truncated = content.length > 300;

  return (
    <div
      className={`my-2 rounded-lg border text-xs ${
        isError
          ? "border-red-800/60 bg-red-950/30"
          : "border-zinc-700 bg-zinc-900/60"
      }`}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-800/50 rounded-lg"
        onClick={() => setExpanded(!expanded)}
      >
        {isError ? (
          <span className="text-red-400">✕</span>
        ) : (
          <span className="text-emerald-400">✓</span>
        )}
        <span className="font-mono text-zinc-400">result</span>
        {isError && <span className="text-red-400 text-[10px] font-medium">ERROR</span>}
        <span className="ml-auto text-zinc-600">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <pre className="px-3 pb-2 overflow-x-auto text-zinc-400 max-h-64 overflow-y-auto whitespace-pre-wrap break-words">
          {content}
        </pre>
      )}
      {!expanded && truncated && (
        <div className="px-3 pb-2 text-zinc-500 truncate">{content.slice(0, 200)}...</div>
      )}
      {!expanded && !truncated && content && (
        <div className="px-3 pb-2 text-zinc-500 whitespace-pre-wrap break-words">{content}</div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "running") return <Spinner size="sm" />;
  if (status === "completed") return <span className="text-emerald-400">✓</span>;
  if (status === "error") return <span className="text-red-400">✕</span>;
  return <span className="text-zinc-500">●</span>;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "text-amber-400 bg-amber-400/10",
    completed: "text-emerald-400 bg-emerald-400/10",
    error: "text-red-400 bg-red-400/10",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors[status] ?? "text-zinc-500"}`}>
      {status}
    </span>
  );
}
