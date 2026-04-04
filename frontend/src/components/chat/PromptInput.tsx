/**
 * PromptInput — message input with submit button and keyboard shortcuts.
 */

import { useState, useRef, useCallback } from "react";
import { useSessionStore } from "../../stores/sessionStore";

interface Props {
  onSend: (content: string) => void;
}

export function PromptInput({ onSend }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = useSessionStore((s) => s.status);
  const isBusy = status === "busy";

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isBusy) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  }, [value, isBusy, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 p-4">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isBusy ? "Working..." : "Type a message... (Enter to send, Shift+Enter for newline)"}
          disabled={isBusy}
          rows={1}
          className="flex-1 resize-none rounded-xl bg-zinc-900 border border-zinc-700 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
          style={{ minHeight: "44px", maxHeight: "200px" }}
        />
        <button
          onClick={handleSubmit}
          disabled={!value.trim() || isBusy}
          className="rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 px-5 py-3 text-sm font-medium text-white transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
