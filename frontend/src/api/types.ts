/**
 * TypeScript types mirroring the backend Pydantic schemas.
 * Single source of truth for the frontend-backend contract.
 */

// === Messages ===

export type Role = "user" | "assistant" | "system";

export interface TextBlock {
  type: "text";
  text: string;
}

export interface ToolUseBlock {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: "tool_result";
  tool_use_id: string;
  content: string;
  is_error: boolean;
}

export type ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock;

export interface Message {
  role: Role;
  content: ContentBlock[] | string;
  message_id: string;
}

// === Sessions ===

export interface SessionInfo {
  session_id: string;
  status: "active" | "idle" | "busy" | "closed";
  model: string;
  created_at: string;
  message_count: number;
  total_cost_usd: number;
}

// === WebSocket Server Events ===

export interface WSAssistantText {
  type: "assistant_text";
  delta: string;
  message_id: string;
}

export interface WSAssistantThinking {
  type: "assistant_thinking";
  delta: string;
  message_id: string;
}

export interface WSMessageStart {
  type: "assistant_message_start";
  message_id: string;
}

export interface WSMessageEnd {
  type: "assistant_message_end";
  message_id: string;
}

export interface WSToolUseStart {
  type: "tool_use_start";
  tool_use_id: string;
  tool_name: string;
  message_id: string;
}

export interface WSToolResult {
  type: "tool_result";
  tool_use_id: string;
  tool_name: string;
  content: string;
  is_error: boolean;
}

export interface WSToolProgress {
  type: "tool_progress";
  tool_use_id: string;
  data: string;
}

export interface WSPermissionRequest {
  type: "permission_request";
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  risk_level: string;
}

export interface WSTurnStart {
  type: "turn_start";
  turn_number: number;
  agent_name: string;
}

export interface WSTurnEnd {
  type: "turn_end";
  stop_reason: string;
  usage: { input_tokens: number; output_tokens: number };
}

export interface WSError {
  type: "error";
  error: string;
  code: string;
}

export interface WSCostUpdate {
  type: "cost_update";
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
}

export interface WSAgentSwitch {
  type: "agent_switch";
  agent_name: string;
  task?: string;
}

export interface WSPipelineStage {
  type: "pipeline_stage";
  stage: string;
  status: string;
  detail: string;
}

export interface WSUIUpdate {
  type: "ui_update";
  artifact_id: string;
  title: string;
  content: string;
  language?: string;
}

export interface WSNotification {
  type: "notification";
  id: string;
  level: string;
  category: string;
  title: string;
  body: string;
  agent_name?: string;
  auto_dismiss_ms: number;
}

export interface WSThinkingProgress {
  type: "thinking_progress";
  agent_name: string;
  phase: string;
  progress_pct: number;
  detail: string;
}

export interface WSToolCallState {
  type: "tool_call_state";
  tool_use_id: string;
  tool_name: string;
  state: "requested" | "approved" | "denied" | "running" | "completed" | "failed";
  is_error: boolean;
  result_preview: string;
}

export type WSServerEvent =
  | WSAssistantText
  | WSAssistantThinking
  | WSMessageStart
  | WSMessageEnd
  | WSToolUseStart
  | WSToolResult
  | WSToolProgress
  | WSPermissionRequest
  | WSTurnStart
  | WSTurnEnd
  | WSError
  | WSCostUpdate
  | WSAgentSwitch
  | WSPipelineStage
  | WSUIUpdate
  | WSNotification
  | WSThinkingProgress
  | WSToolCallState;

// === Tools ===

export interface ToolSpec {
  name: string;
  description: string;
  risk_level: string;
  is_read_only: boolean;
}
