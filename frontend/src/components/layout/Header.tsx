/**
 * Header — HUD with model selector, cost, token usage.
 * Phase 2: Added model selector dropdown for multi-model support.
 */

import { useState, useEffect } from "react";
import { useSessionStore } from "../../stores/sessionStore";
import { ws } from "../../api/ws";
import { api } from "../../api/client";

interface ModelEntry {
  id: string;
  owned_by: string;
}

export function Header() {
  const model = useSessionStore((s) => s.model);
  const status = useSessionStore((s) => s.status);
  const wsStatus = useSessionStore((s) => s.wsStatus);
  const totalCost = useSessionStore((s) => s.totalCostUsd);
  const inputTokens = useSessionStore((s) => s.inputTokens);
  const outputTokens = useSessionStore((s) => s.outputTokens);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [showSelector, setShowSelector] = useState(false);

  useEffect(() => {
    api.models.list().then((res) => setModels(res.data ?? [])).catch(() => {});
  }, []);

  const handleModelChange = (newModel: string) => {
    ws.send({ type: "session_config", model: newModel });
    useSessionStore.getState().setModel(newModel);
    setShowSelector(false);
  };

  const statusColor =
    status === "busy"
      ? "bg-amber-500"
      : wsStatus === "connected"
        ? "bg-emerald-500"
        : "bg-zinc-600";

  const providerColor: Record<string, string> = {
    anthropic: "text-orange-400",
    openai: "text-green-400",
    google: "text-blue-400",
    xai: "text-cyan-400",
    deepseek: "text-indigo-400",
    ollama: "text-pink-400",
  };

  const currentProvider = models.find((m) => m.id === model)?.owned_by ?? "anthropic";

  return (
    <header className="h-12 border-b border-zinc-800 bg-zinc-950 flex items-center justify-between px-4 relative">
      {/* Left: Status + Model selector */}
      <div className="flex items-center gap-3">
        <span className={`w-2 h-2 rounded-full ${statusColor}`} />
        <button
          onClick={() => setShowSelector(!showSelector)}
          className={`text-sm font-medium hover:text-white transition-colors ${providerColor[currentProvider] ?? "text-zinc-300"}`}
        >
          {model || "Select model"} ▾
        </button>
        <span className="text-xs text-zinc-600">
          {status === "busy" ? "Working..." : wsStatus}
        </span>

        {/* Model dropdown */}
        {showSelector && (
          <div className="absolute top-12 left-12 z-50 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-64">
            {Object.entries(
              models.reduce<Record<string, ModelEntry[]>>((acc, m) => {
                const p = m.owned_by;
                if (!acc[p]) acc[p] = [];
                acc[p].push(m);
                return acc;
              }, {}),
            ).map(([provider, providerModels]) => (
              <div key={provider}>
                <div className="px-3 py-1 text-xs text-zinc-500 uppercase tracking-wider">
                  {provider}
                </div>
                {providerModels.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => handleModelChange(m.id)}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors ${
                      m.id === model
                        ? `${providerColor[provider] ?? "text-zinc-200"} font-medium`
                        : "text-zinc-300"
                    }`}
                  >
                    {m.id}
                    {m.id === model && " ✓"}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right: Cost + Tokens */}
      <div className="flex items-center gap-4 text-xs text-zinc-500">
        <span>
          In: {inputTokens.toLocaleString()} / Out: {outputTokens.toLocaleString()}
        </span>
        <span className="text-amber-400 font-mono">
          ${totalCost.toFixed(4)}
        </span>
      </div>
    </header>
  );
}
