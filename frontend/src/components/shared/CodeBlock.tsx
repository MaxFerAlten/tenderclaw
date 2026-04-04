/**
 * CodeBlock — syntax-highlighted code display.
 */

interface Props {
  code: string;
  language?: string;
}

export function CodeBlock({ code, language }: Props) {
  return (
    <div className="my-2 rounded-lg overflow-hidden border border-zinc-700">
      {language && (
        <div className="bg-zinc-800 px-3 py-1 text-xs text-zinc-400 border-b border-zinc-700">
          {language}
        </div>
      )}
      <pre className="bg-zinc-900 px-4 py-3 overflow-x-auto">
        <code className="text-sm font-mono text-zinc-200">{code}</code>
      </pre>
    </div>
  );
}
