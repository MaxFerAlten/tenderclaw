/**
 * ChatView — main conversation view with message list and input.
 * The primary interaction surface for TenderClaw.
 */

import { useEffect, useCallback } from "react";
import { MessageList } from "./MessageList";
import { PromptInput } from "./PromptInput";
import { useSessionStore } from "../../stores/sessionStore";
import { ws } from "../../api/ws";
import { api } from "../../api/client";

export function ChatView() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const setSession = useSessionStore((s) => s.setSession);
  const addUserMessage = useSessionStore((s) => s.addUserMessage);
  const handleServerEvent = useSessionStore((s) => s.handleServerEvent);
  const setWsStatus = useSessionStore((s) => s.setWsStatus);

  // Create session and connect WebSocket on mount
  useEffect(() => {
    if (sessionId) return;

    const init = async () => {
      try {
        const res = await api.sessions.create({
          working_directory: ".",
        });
        setSession(res.session_id, "claude-sonnet-4-20250514");

        // Connect WebSocket
        ws.connect(res.session_id);
        ws.onEvent(handleServerEvent);
        ws.onStatus(setWsStatus);
      } catch (err) {
        console.error("Failed to create session:", err);
      }
    };

    init();

    return () => {
      ws.disconnect();
    };
  }, [sessionId, setSession, handleServerEvent, setWsStatus]);

  const handleSend = useCallback(
    (content: string) => {
      addUserMessage(content);
      ws.sendUserMessage(content);
    },
    [addUserMessage],
  );

  return (
    <div className="flex flex-col h-full">
      <MessageList />
      <PromptInput onSend={handleSend} />
    </div>
  );
}
