/** CostBadge — displays session cost in the UI. */

import { useEffect, useState } from "react";
import { DollarSign } from "lucide-react";
import type { CostSummary } from "../../types/cost";

interface CostBadgeProps {
  compact?: boolean;
}

export function CostBadge({ compact = false }: CostBadgeProps) {
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCost();
    const interval = setInterval(fetchCost, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchCost = async () => {
    try {
      const res = await fetch("/api/costs/current");
      if (res.ok) {
        setCost(await res.json());
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <span className="text-zinc-500">...</span>;
  if (!cost) return null;

  if (compact) {
    return (
      <span className="flex items-center gap-1 text-zinc-400 text-sm">
        <DollarSign className="w-3 h-3" />
        {formatCost(cost.total_cost_usd)}
      </span>
    );
  }

  return (
    <div className="bg-zinc-800 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-zinc-400 text-sm">Session Cost</span>
        <span className="text-emerald-400 font-semibold">
          ${cost.total_cost_usd.toFixed(4)}
        </span>
      </div>
      <div className="space-y-1">
        {Object.entries(cost.model_usage).map(([model, usage]) => (
          <div key={model} className="flex justify-between text-xs">
            <span className="text-zinc-500 truncate">{model}</span>
            <span className="text-zinc-400">${usage.cost_usd.toFixed(4)}</span>
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-zinc-500 pt-1 border-t border-zinc-700">
        <span>Tokens: {cost.total_input_tokens.toLocaleString()} / {cost.total_output_tokens.toLocaleString()}</span>
      </div>
    </div>
  );
}

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  if (cost < 1) return `$${cost.toFixed(3)}`;
  return `$${cost.toFixed(2)}`;
}
