/**
 * Session state store (Zustand).
 * Manages the active session, messages, streaming state, and tool results.
 */

import { create } from "zustand";
import type { Message, ContentBlock, WSServerEvent } from "../api/types";
import type { KeywordMapping } from "../api/keywordsApi";

interface Artifact {
  artifact_id: string;
  title: string;
  content: string;
  language?: string;
}

interface ToolState {
  tool_use_id: string;
  tool_name: string;
  status: "running" | "completed" | "error";
  result?: string;
}

export interface PermissionRequest {
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  risk_level: string;
}

interface SessionStore {
  // Session
  sessionId: string | null;
  model: string;
  status: "idle" | "busy" | "disconnected";
  wsStatus: "connecting" | "connected" | "disconnected";
  activeAgent: string;

  // Messages
  messages: Message[];
  streamingText: string;
  streamingMessageId: string;
  pendingBlocks: ContentBlock[];

  // Tools
  activeTools: Map<string, ToolState>;

  // Permissions
  permissionQueue: PermissionRequest[];

  // Cost
  totalCostUsd: number;
  inputTokens: number;
  outputTokens: number;
  perMessageCosts: Array<{ messageId: string; inputTokens: number; outputTokens: number; costUsd: number }>;

  // Artifacts (A2UI)
  artifacts: Map<string, Artifact>;
  activeArtifactId: string | null;

  // Keyword detection
  detectedKeyword: KeywordMapping | null;

  // Actions
  getMessageCost: (messageId: string) => { inputTokens: number; outputTokens: number; costUsd: number } | null;
  setSession: (sessionId: string, model: string) => void;
  setModel: (model: string) => void;
  addUserMessage: (content: string) => void;
  handleServerEvent: (event: WSServerEvent) => void;
  setWsStatus: (status: "connecting" | "connected" | "disconnected") => void;
  removePermissionRequest: (toolUseId: string) => void;
  setDetectedKeyword: (keyword: KeywordMapping | null) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  sessionId: null,
  model: "",
  status: "idle",
  wsStatus: "disconnected",
  messages: [],
  streamingText: "",
  streamingMessageId: "",
  pendingBlocks: [],
  activeAgent: "sisyphus",
  activeTools: new Map(),
  permissionQueue: [],
  totalCostUsd: 0,
  inputTokens: 0,
  outputTokens: 0,
  perMessageCosts: [],
  artifacts: new Map(),
  activeArtifactId: null,
  detectedKeyword: null,

  getMessageCost: (messageId) => {
    const found = get().perMessageCosts.find((p) => p.messageId === messageId);
    return found ?? null;
  },

  setSession: (sessionId, model) =>
    set({ sessionId, model, messages: [], status: "idle", perMessageCosts: [] }),

  setModel: (model) => set({ model }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { role: "user", content, message_id: `local_${Date.now()}` },
      ],
      status: "busy",
    })),

  setWsStatus: (wsStatus) => set({ wsStatus }),

  removePermissionRequest: (toolUseId) =>
    set((s) => ({
      permissionQueue: s.permissionQueue.filter((r) => r.tool_use_id !== toolUseId),
    })),

  setDetectedKeyword: (keyword) => set({ detectedKeyword: keyword }),

  reset: () =>
    set({
      sessionId: null,
      model: "",
      status: "idle",
      messages: [],
      streamingText: "",
      streamingMessageId: "",
      pendingBlocks: [],
      activeTools: new Map(),
      permissionQueue: [],
      totalCostUsd: 0,
      perMessageCosts: [],
      detectedKeyword: null,
    }),

  handleServerEvent: (event) => {
    const state = get();

    switch (event.type) {
      case "assistant_message_start":
        set({ streamingText: "", streamingMessageId: event.message_id, pendingBlocks: [] });
        break;

      case "assistant_text":
        set({ streamingText: state.streamingText + event.delta });
        break;

      case "assistant_message_end": {
        // Build content blocks: text + accumulated tool blocks
        const blocks: ContentBlock[] = [];
        if (state.streamingText) {
          blocks.push({ type: "text", text: state.streamingText });
        }
        blocks.push(...state.pendingBlocks);

        if (blocks.length > 0) {
          const msg: Message = {
            role: "assistant",
            content: blocks.length === 1 && blocks[0].type === "text"
              ? (blocks[0] as { text: string }).text
              : blocks,
            message_id: event.message_id,
          };
          set((s) => ({
            messages: [...s.messages, msg],
            streamingText: "",
            streamingMessageId: "",
            pendingBlocks: [],
          }));
        }
        break;
      }

      case "tool_use_start": {
        const tools = new Map(state.activeTools);
        tools.set(event.tool_use_id, {
          tool_use_id: event.tool_use_id,
          tool_name: event.tool_name,
          status: "running",
        });
        // Accumulate tool_use block into pending message
        const tuBlock: ContentBlock = {
          type: "tool_use",
          id: event.tool_use_id,
          name: event.tool_name,
          input: {},
        };
        set((s) => ({ activeTools: tools, pendingBlocks: [...s.pendingBlocks, tuBlock] }));
        break;
      }

      case "tool_result": {
        const tools = new Map(state.activeTools);
        tools.set(event.tool_use_id, {
          tool_use_id: event.tool_use_id,
          tool_name: event.tool_name,
          status: event.is_error ? "error" : "completed",
          result: event.content,
        });
        // Accumulate tool_result block into pending message
        const trBlock: ContentBlock = {
          type: "tool_result",
          tool_use_id: event.tool_use_id,
          content: event.content,
          is_error: event.is_error,
        };
        set((s) => ({ activeTools: tools, pendingBlocks: [...s.pendingBlocks, trBlock] }));
        break;
      }

      case "permission_request":
        set((s) => ({
          permissionQueue: [...s.permissionQueue, {
            tool_use_id: event.tool_use_id,
            tool_name: event.tool_name,
            tool_input: event.tool_input,
            risk_level: event.risk_level,
          }],
        }));
        break;

      case "turn_start":
        set({ status: "busy", activeAgent: event.agent_name || "sisyphus" });
        break;

      case "turn_end":
        set({ status: "idle", activeAgent: "sisyphus" });
        break;

      case "agent_switch":
        set({ activeAgent: event.agent_name });
        break;

      case "cost_update": {
        const prevInput = state.inputTokens;
        const prevOutput = state.outputTokens;
        const deltaIn = event.input_tokens - prevInput;
        const deltaOut = event.output_tokens - prevOutput;
        const deltaCost = event.total_cost_usd - state.totalCostUsd;
        const msgId = state.streamingMessageId || `cost_${Date.now()}`;
        set((s) => ({
          totalCostUsd: event.total_cost_usd,
          inputTokens: event.input_tokens,
          outputTokens: event.output_tokens,
          perMessageCosts: [
            ...s.perMessageCosts,
            { messageId: msgId, inputTokens: Math.max(0, deltaIn), outputTokens: Math.max(0, deltaOut), costUsd: Math.max(0, deltaCost) },
          ],
        }));
        break;
      }

      case "ui_update": {
        const artifacts = new Map(state.artifacts);
        artifacts.set(event.artifact_id, {
          artifact_id: event.artifact_id,
          title: event.title,
          content: event.content,
          language: event.language,
        });
        set({ artifacts, activeArtifactId: event.artifact_id });
        break;
      }

      case "error":
        // Session was lost (backend restart) — reset so ChatView creates a new one
        if ((event as { code?: string }).code === "session_not_found") {
          set({ sessionId: null, status: "idle", messages: [], streamingText: "" });
        } else {
          // Show error as a visible assistant message in the chat
          const errMsg: Message = {
            role: "assistant",
            content: `⚠️ ${event.error}`,
            message_id: `err_${Date.now()}`,
          };
          set((s) => ({
            status: "idle",
            messages: [...s.messages, errMsg],
          }));
        }
        console.error("Server error:", event.error);
        break;
    }
  },
}));
