/**
 * KeywordBadge — displays detected keyword trigger in the UI.
 */

import { Zap } from "lucide-react";
import type { KeywordMapping } from "../../api/keywordsApi";

interface KeywordBadgeProps {
  keyword: KeywordMapping;
}

export function KeywordBadge({ keyword }: KeywordBadgeProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-600/20 border border-violet-500/50 text-violet-300 text-xs">
      <Zap className="w-3.5 h-3.5" />
      <span className="font-medium">{keyword.action}</span>
      <span className="text-violet-400/70">— {keyword.description}</span>
    </div>
  );
}
