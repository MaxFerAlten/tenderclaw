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

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
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

    const init = async () => {
      try {
        const savedModel = localStorage.getItem("tenderclaw_model") || "claude-sonnet-4-20250514";
        const res = await api.sessions.create({ working_directory: ".", model: savedModel });
        if (!mountedRef.current) return;
        setSession(res.session_id, savedModel);
        ws.connect(res.session_id);
        ws.onEvent((e) => handleServerEventRef.current(e));
        ws.onStatus((s) => setWsStatusRef.current(s));
      } catch (err) {
        console.error("Failed to create session:", err);
      }
    };

    init();

    return () => {
      if (!mountedRef.current) {
        ws.disconnect();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleSend = useCallback(
    async (content: string) => {
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
      addUserMessage(content);
      ws.sendUserMessage(content);
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
