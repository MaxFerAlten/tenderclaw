/**
 * ChatView — main conversation view with message list and input.
 * The primary interaction surface for TenderClaw.
 */

import { useEffect, useCallback, useRef } from "react";
import { MessageList } from "./MessageList";
import { PromptInput } from "./PromptInput";
import { KeywordBadge } from "./KeywordBadge";
import { useSessionStore } from "../../stores/sessionStore";
import { useKeybindingContext } from "../../keybindings";
import { ws } from "../../api/ws";
import { api } from "../../api/client";
import type { ChatAttachment, PowerLevel } from "../../api/types";
import { keywordsApi } from "../../api/keywordsApi";

export function ChatView() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const setSession = useSessionStore((s) => s.setSession);
  const addUserMessage = useSessionStore((s) => s.addUserMessage);
  const handleServerEvent = useSessionStore((s) => s.handleServerEvent);
  const setWsStatus = useSessionStore((s) => s.setWsStatus);
  const detectedKeyword = useSessionStore((s) => s.detectedKeyword);
  const setDetectedKeyword = useSessionStore((s) => s.setDetectedKeyword);
  const { setContext } = useKeybindingContext();

  // Stable refs so the effect never re-runs due to store function identity changes
  const handleServerEventRef = useRef(handleServerEvent);
  const setWsStatusRef = useRef(setWsStatus);
  handleServerEventRef.current = handleServerEvent;
  setWsStatusRef.current = setWsStatus;

  useEffect(() => {
    const unsubscribeEvent = ws.onEvent((e) => handleServerEventRef.current(e));
    const unsubscribeStatus = ws.onStatus((s) => setWsStatusRef.current(s));

    return () => {
      unsubscribeEvent();
      unsubscribeStatus();
      ws.disconnect();
    };
  }, []);

  useEffect(() => {
    setContext("Chat");
  }, [setContext]);

  useEffect(() => {
    if (sessionId) {
      // Session exists — ensure WS is connected
      if (ws.isDisconnected()) {
        ws.connect(sessionId);
      }
      return;
    }

    const controller = new AbortController();

    const init = async () => {
      try {
        const savedModel = localStorage.getItem("tenderclaw_model") || "claude-sonnet-4-20250514";
        const res = await api.sessions.create({ working_directory: ".", model: savedModel }, controller.signal);
        setSession(res.session_id, savedModel);
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "AbortError") return;
        console.error("Failed to create session:", err);
      }
    };

    void init();

    return () => {
      controller.abort();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleSend = useCallback(
    async (content: string, attachments: ChatAttachment[], powerLevel: PowerLevel) => {
      if (content.trim()) {
        try {
          const result = await keywordsApi.detect(content);
          if (result.primary_action && result.matches.length > 0) {
            setDetectedKeyword(result.matches[0]);
          } else {
            setDetectedKeyword(null);
          }
        } catch {
          setDetectedKeyword(null);
        }
      } else {
        setDetectedKeyword(null);
      }
      addUserMessage(content, attachments);
      ws.sendUserMessage(content, attachments, powerLevel);
    },
    [addUserMessage, setDetectedKeyword],
  );

  return (
    <div className="flex flex-col h-full">
      {detectedKeyword && (
        <div className="px-4 pt-3">
          <KeywordBadge keyword={detectedKeyword} />
        </div>
      )}
      <MessageList />
      <PromptInput onSend={handleSend} />
    </div>
  );
}
