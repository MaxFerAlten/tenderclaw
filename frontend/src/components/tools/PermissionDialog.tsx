/**
 * PermissionDialog — modal for approving/denying tool execution.
 * Shows when backend sends a permission_request event for medium/high risk tools.
 *
 * Keyboard shortcuts: Y = approve, N / Escape = deny
 * "Always allow" checkbox: appends alwaysAllow=true to the permission response
 */

import { useEffect, useRef, useState } from "react";
import { useSessionStore } from "../../stores/sessionStore";

interface Props {
  sendPermissionResponse: (
    toolUseId: string,
    decision: "approve" | "deny",
    alwaysAllow?: boolean,
  ) => void;
}

export function PermissionDialog({ sendPermissionResponse }: Props) {
  const queue = useSessionStore((s) => s.permissionQueue);
  const removeRequest = useSessionStore((s) => s.removePermissionRequest);
  const [alwaysAllow, setAlwaysAllow] = useState(false);
  const approveRef = useRef<HTMLButtonElement>(null);

  const req = queue[0];

  // Reset "always allow" whenever a new request surfaces
  useEffect(() => {
    setAlwaysAllow(false);
    // Focus the approve button so Enter/Space also work
    approveRef.current?.focus();
  }, [req?.tool_use_id]);

  // Keyboard shortcuts: Y = approve, N / Escape = deny
  useEffect(() => {
    if (!req) return;
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement) return; // don't intercept checkbox/text inputs
      if (e.key === "y" || e.key === "Y") {
        e.preventDefault();
        handleDecision("approve");
      } else if (e.key === "n" || e.key === "N" || e.key === "Escape") {
        e.preventDefault();
        handleDecision("deny");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [req?.tool_use_id, alwaysAllow]);

  if (!req) return null;

  const riskColors: Record<string, string> = {
    high: "text-red-400 bg-red-400/10 border-red-800",
    medium: "text-amber-400 bg-amber-400/10 border-amber-800",
    low: "text-emerald-400 bg-emerald-400/10 border-emerald-800",
  };
  const riskStyle = riskColors[req.risk_level] ?? riskColors.medium;

  function handleDecision(decision: "approve" | "deny") {
    sendPermissionResponse(req.tool_use_id, decision, decision === "approve" ? alwaysAllow : false);
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

        {/* Always allow */}
        <label className="flex items-center gap-2 mb-4 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={alwaysAllow}
            onChange={(e) => setAlwaysAllow(e.target.checked)}
            className="w-3.5 h-3.5 accent-violet-500"
          />
          <span className="text-[11px] text-zinc-400">Always allow this tool in this session</span>
        </label>

        {/* Keyboard hint */}
        <p className="text-[10px] text-zinc-600 mb-3 text-center">
          <kbd className="px-1 bg-zinc-800 rounded text-zinc-400">Y</kbd> approve &nbsp;·&nbsp;
          <kbd className="px-1 bg-zinc-800 rounded text-zinc-400">N</kbd> /
          <kbd className="px-1 bg-zinc-800 rounded text-zinc-400">Esc</kbd> deny
        </p>

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
            ref={approveRef}
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
