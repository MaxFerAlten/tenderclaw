/**
 * TokenBadge — inline cost + token display for a single assistant message.
 * Shown as a subtle badge below each assistant bubble.
 */

interface TokenBadgeProps {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export function TokenBadge({ inputTokens, outputTokens, costUsd }: TokenBadgeProps) {
  if (inputTokens === 0 && outputTokens === 0) return null;

  const costLabel =
    costUsd < 0.0001
      ? "<$0.0001"
      : costUsd < 0.01
        ? `$${costUsd.toFixed(4)}`
        : `$${costUsd.toFixed(3)}`;

  return (
    <div className="flex items-center gap-2 mt-1 text-xs text-zinc-600 select-none">
      <span title="Input tokens">↑{inputTokens.toLocaleString()}</span>
      <span className="text-zinc-700">·</span>
      <span title="Output tokens">↓{outputTokens.toLocaleString()}</span>
      {costUsd > 0 && (
        <>
          <span className="text-zinc-700">·</span>
          <span className="text-amber-700/80 font-mono">{costLabel}</span>
        </>
      )}
    </div>
  );
}
