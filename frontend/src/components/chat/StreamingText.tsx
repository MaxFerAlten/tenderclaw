/**
 * StreamingText — renders live-streamed assistant text with a cursor.
 */

interface Props {
  text: string;
}

export function StreamingText({ text }: Props) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-xl px-4 py-3 bg-zinc-900 border border-zinc-800">
        <div className="text-xs font-medium text-violet-400 mb-1">
          TenderClaw
        </div>
        <div className="text-sm leading-relaxed whitespace-pre-wrap text-zinc-100">
          {text}
          <span className="inline-block w-2 h-4 bg-violet-500 animate-pulse ml-0.5" />
        </div>
      </div>
    </div>
  );
}
