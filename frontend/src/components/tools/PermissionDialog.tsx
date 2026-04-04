/**
 * PermissionDialog — modal for approving/denying tool execution.
 * Shows when backend sends a permission_request event for medium/high risk tools.
 */

import { useSessionStore } from "../../stores/sessionStore";

interface Props {
  sendPermissionResponse: (toolUseId: string, decision: "approve" | "deny") => void;
}

export function PermissionDialog({ sendPermissionResponse }: Props) {
  const queue = useSessionStore((s) => s.permissionQueue);
  const removeRequest = useSessionStore((s) => s.removePermissionRequest);

  if (queue.length === 0) return null;

  const req = queue[0];

  const riskColors: Record<string, string> = {
    high: "text-red-400 bg-red-400/10 border-red-800",
    medium: "text-amber-400 bg-amber-400/10 border-amber-800",
    low: "text-emerald-400 bg-emerald-400/10 border-emerald-800",
  };
  const riskStyle = riskColors[req.risk_level] ?? riskColors.medium;

  function handleDecision(decision: "approve" | "deny") {
    sendPermissionResponse(req.tool_use_id, decision);
    removeRequest(req.tool_use_id);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl p-5">
        {/* Header */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-amber-400 text-lg">⚠</span>
          <h3 className="text-sm font-semibold text-zinc-100">Permission Required</h3>
          {queue.length > 1 && (
            <span className="ml-auto text-[10px] text-zinc-500">+{queue.length - 1} more</span>
          )}
        </div>

        {/* Tool info */}
        <div className="space-y-3 mb-5">
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500">Tool:</span>
            <span className="font-mono text-xs font-semibold text-violet-400">{req.tool_name}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${riskStyle}`}>
              {req.risk_level}
            </span>
          </div>

          {Object.keys(req.tool_input).length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-zinc-500 hover:text-zinc-300">
                Input parameters
              </summary>
              <pre className="mt-1 rounded-lg bg-zinc-950 border border-zinc-800 p-2 overflow-x-auto text-zinc-400 max-h-40 overflow-y-auto">
                {JSON.stringify(req.tool_input, null, 2)}
              </pre>
            </details>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => handleDecision("deny")}
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700 transition"
          >
            Deny
          </button>
          <button
            type="button"
            onClick={() => handleDecision("approve")}
            className="flex-1 rounded-lg bg-violet-600 px-4 py-2 text-xs font-medium text-white hover:bg-violet-500 transition"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
