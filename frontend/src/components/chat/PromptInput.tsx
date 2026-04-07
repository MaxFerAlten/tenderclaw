/**
 * PromptInput — message input with submit button and keyboard shortcuts.
 */

import { useState, useRef, useCallback } from "react";
import { Square } from "lucide-react";
import { useSessionStore } from "../../stores/sessionStore";
import { ws } from "../../api/ws";
import { VoiceButton } from "../voice/VoiceButton";
import { useVoiceMode } from "../voice/useVoiceMode";

interface Props {
  onSend: (content: string) => void;
}

export function PromptInput({ onSend }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = useSessionStore((s) => s.status);
  const isBusy = status === "busy";

  const { isListening, isSupported, toggleListening } = useVoiceMode({
    onTranscript: (t) => {
      if (t.final) {
        setValue((prev) => prev + " " + t.final);
      }
    },
  });

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isBusy) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  }, [value, isBusy, onSend]);

  const handleStop = useCallback(() => {
    ws.sendAbort();
  }, []);

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
      <div className="flex items-end gap-3 max-w-3xl mx-auto">
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
        <VoiceButton
          isListening={isListening}
          isSupported={isSupported}
          onClick={toggleListening}
          size="md"
        />
        {isBusy ? (
          <button
            onClick={handleStop}
            className="rounded-xl bg-red-600 hover:bg-red-500 px-5 py-3 text-sm font-medium text-white transition-colors flex items-center gap-2"
          >
            <Square className="w-4 h-4" />
            Stop
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!value.trim()}
            className="rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 px-5 py-3 text-sm font-medium text-white transition-colors"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
