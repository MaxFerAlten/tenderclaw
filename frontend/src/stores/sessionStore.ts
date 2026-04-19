/**
 * Session state store (Zustand).
 * Manages the active session, messages, streaming state, and tool results.
 */

import { create } from "zustand";
import type { ChatAttachment, Message, ContentBlock, WSServerEvent } from "../api/types";
import type { KeywordMapping } from "../api/keywordsApi";
import { useNotificationStore } from "./notificationStore";

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
  jsonBuffer?: string;
}

export interface ToolCallStateItem {
  tool_use_id: string;
  tool_name: string;
  state: "requested" | "approved" | "denied" | "running" | "completed" | "failed";
  is_error: boolean;
  result_preview: string;
  updated_at: number;
}

export interface PipelineStageState {
  stage: string;
  status: "pending" | "started" | "completed" | "failed" | "skipped";
  detail: string;
  startedAt?: number;
  completedAt?: number;
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

  // Pipeline
  pipelineActive: boolean;
  pipelineStages: PipelineStageState[];
  turnCount: number;
  turnStartedAt: number | null;

  // Artifacts (A2UI)
  artifacts: Map<string, Artifact>;
  activeArtifactId: string | null;

  // Tool call state machine (WSToolCallStateUpdate)
  toolCallStates: Map<string, ToolCallStateItem>;

  // Keyword detection
  detectedKeyword: KeywordMapping | null;

  // Actions
  getMessageCost: (messageId: string) => { inputTokens: number; outputTokens: number; costUsd: number } | null;
  setSession: (sessionId: string, model: string) => void;
  setModel: (model: string) => void;
  addUserMessage: (content: string, attachments?: ChatAttachment[]) => void;
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
  pipelineActive: false,
  pipelineStages: [],
  turnCount: 0,
  turnStartedAt: null,
  artifacts: new Map(),
  activeArtifactId: null,
  detectedKeyword: null,
  toolCallStates: new Map(),

  getMessageCost: (messageId) => {
    const found = get().perMessageCosts.find((p) => p.messageId === messageId);
    return found ?? null;
  },

  setSession: (sessionId, model) =>
    set({ sessionId, model, messages: [], status: "idle", perMessageCosts: [] }),

  setModel: (model) => set({ model }),

  addUserMessage: (content, attachments = []) =>
    set((s) => {
      const trimmed = content.trim();
      const messageContent: Message["content"] = attachments.length > 0
        ? [
            ...(trimmed ? [{ type: "text" as const, text: trimmed }] : []),
            ...attachments.map((attachment) => ({
              type: "image" as const,
              source: attachment.url,
              mime_type: attachment.type,
              name: attachment.name,
              size_bytes: attachment.size_bytes,
            })),
          ]
        : content;

      return {
        messages: [
          ...s.messages,
          { role: "user", content: messageContent, message_id: `local_${Date.now()}` },
        ],
        status: "busy",
      };
    }),

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
      pipelineActive: false,
      pipelineStages: [],
      turnCount: 0,
      turnStartedAt: null,
      detectedKeyword: null,
      toolCallStates: new Map(),
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
          jsonBuffer: "",
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

      case "input_json_delta": {
        const tools = new Map(state.activeTools);
        const existing = tools.get(event.tool_use_id);
        let parsed: Record<string, unknown> = {};
        if (existing) {
          const jsonBuffer = (existing.jsonBuffer || "") + event.partial_json;
          try {
            parsed = JSON.parse(jsonBuffer);
          } catch {
            // Partial JSON — not yet complete, keep accumulating
          }
          tools.set(event.tool_use_id, { ...existing, jsonBuffer, status: "running" });
        }
        set((s) => ({
          activeTools: tools,
          pendingBlocks: s.pendingBlocks.map((b) =>
            b.type === "tool_use" && b.id === event.tool_use_id ? { ...b, input: parsed } : b
          ),
        }));
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
        set((s) => ({
          status: "busy",
          activeAgent: event.agent_name || "sisyphus",
          turnCount: s.turnCount + 1,
          turnStartedAt: Date.now(),
        }));
        break;

      case "turn_end":
        set({ status: "idle", activeAgent: "sisyphus" });
        break;

      case "pipeline_stage": {
        const stages = [...state.pipelineStages];
        const existing = stages.findIndex((s) => s.stage === event.stage);
        const entry: PipelineStageState = {
          stage: event.stage,
          status: event.status as PipelineStageState["status"],
          detail: event.detail || "",
          startedAt: event.status === "started" ? Date.now() : stages[existing]?.startedAt,
          completedAt: event.status === "completed" || event.status === "failed" ? Date.now() : undefined,
        };
        if (existing >= 0) {
          stages[existing] = entry;
        } else {
          stages.push(entry);
        }
        set({ pipelineActive: true, pipelineStages: stages });
        break;
      }

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

      case "notification": {
        useNotificationStore.getState().addNotification({
          id: event.id,
          level: event.level as "info" | "success" | "warning" | "error",
          category: event.category as "agent" | "tool" | "pipeline" | "system" | "security",
          title: event.title,
          body: event.body,
          agentName: event.agent_name,
          autoDismissMs: event.auto_dismiss_ms,
        });
        break;
      }

      case "thinking_progress": {
        useNotificationStore.getState().setThinking({
          agentName: event.agent_name,
          phase: event.phase,
          progressPct: event.progress_pct,
          detail: event.detail,
          active: true,
        });
        break;
      }

      case "tool_call_state": {
        const states = new Map(state.toolCallStates);
        states.set(event.tool_use_id, {
          tool_use_id: event.tool_use_id,
          tool_name: event.tool_name,
          state: event.state as ToolCallStateItem["state"],
          is_error: event.is_error ?? false,
          result_preview: event.result_preview ?? "",
          updated_at: Date.now(),
        });
        set({ toolCallStates: states });
        break;
      }

      case "assistant_thinking":
        // Thinking deltas handled by streaming — no extra state needed
        break;

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
          set((s) => {
            const blocks: ContentBlock[] = [];
            if (s.streamingText) blocks.push({ type: "text", text: s.streamingText });
            blocks.push(...s.pendingBlocks);
            
            const msgs = [...s.messages];
            if (blocks.length > 0) {
              msgs.push({
                role: "assistant",
                content: blocks.length === 1 && blocks[0].type === "text"
                  ? (blocks[0] as { text: string }).text
                  : blocks,
                message_id: s.streamingMessageId || `partial_${Date.now()}`,
              });
            }
            msgs.push(errMsg);

            return {
              status: "idle",
              messages: msgs,
              streamingText: "",
              streamingMessageId: "",
              pendingBlocks: [],
            };
          });
        }
        console.error("Server error:", event.error);
        break;
    }
  },
}));
