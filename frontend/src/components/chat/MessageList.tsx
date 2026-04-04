/**
 * MessageList — scrollable list of conversation messages.
 */

import { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { StreamingText } from "./StreamingText";
import { useSessionStore } from "../../stores/sessionStore";

export function MessageList() {
  const messages = useSessionStore((s) => s.messages);
  const streamingText = useSessionStore((s) => s.streamingText);
  const status = useSessionStore((s) => s.status);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingText]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-4 space-y-4">
        {messages.length === 0 && !streamingText && (
          <div className="flex items-center justify-center h-full min-h-[50vh]">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-zinc-400 mb-2">
                TenderClaw
              </h2>
              <p className="text-zinc-600 text-sm max-w-md">
                Multi-agent, multi-model AI coding assistant.
                Type a message to begin.
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.message_id} message={msg} />
        ))}

        {streamingText && <StreamingText text={streamingText} />}

        {status === "busy" && !streamingText && (
          <div className="flex items-center gap-2 text-zinc-500 text-sm">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
