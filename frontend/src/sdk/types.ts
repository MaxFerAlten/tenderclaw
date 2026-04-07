/**
 * TenderClaw Agent SDK - TypeScript Types
 * Type definitions corresponding to shared/sdk_types.py
 */

export enum AgentMode {
  Primary = "primary",
  Subagent = "subagent",
}

export enum AgentCategory {
  Orchestration = "orchestration",
  Exploration = "exploration",
  Advisor = "advisor",
  Specialist = "specialist",
  Utility = "utility",
}

export enum AgentCost {
  Free = "free",
  Cheap = "cheap",
  Expensive = "expensive",
}

export interface AgentConfig {
  name: string;
  model?: string;
  system_prompt?: string;
  tools?: string[];
  max_tokens?: number;
  timeout?: number;
  stream?: boolean;
}

export interface AgentManifest {
  name: string;
  description: string;
  mode: AgentMode;
  default_model: string;
  category: AgentCategory;
  cost: AgentCost;
  system_prompt: string;
  max_tokens: number;
  tools: string[];
  enabled: boolean;
  is_builtin: boolean;
}

export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: unknown;
}

export interface ToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  parameters: ToolParameter[];
  risk_level: string;
  is_read_only: boolean;
}

export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResult {
  id: string;
  name: string;
  content: string;
  is_error: boolean;
  duration_ms: number;
}

export enum MessageRole {
  User = "user",
  Assistant = "assistant",
  System = "system",
  Tool = "tool",
}

export enum ContentBlockType {
  Text = "text",
  ToolUse = "tool_use",
  ToolResult = "tool_result",
  Thinking = "thinking",
  Image = "image",
}

export interface TextContent {
  type: ContentBlockType.Text;
  text: string;
}

export interface ToolUseContent {
  type: ContentBlockType.ToolUse;
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultContent {
  type: ContentBlockType.ToolResult;
  tool_use_id: string;
  content: string;
  is_error: boolean;
}

export type ContentBlock = TextContent | ToolUseContent | ToolResultContent;

export interface Message {
  role: MessageRole;
  content: string | ContentBlock[];
  message_id?: string;
  timestamp?: string;
}

export enum SessionStatus {
  Active = "active",
  Idle = "idle",
  Busy = "busy",
  Closed = "closed",
}

export interface Session {
  session_id: string;
  status: SessionStatus;
  model: string;
  created_at: string;
  message_count: number;
  working_directory: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_tokens: number;
  cache_read_tokens: number;
  total_tokens?: number;
}

export interface AgentResponse {
  session_id: string;
  message: Message;
  stop_reason: string;
  usage: TokenUsage;
  cost_usd: number;
  agent_name: string;
}

export enum StreamEventType {
  Delta = "delta",
  ToolCall = "tool_call",
  ToolResult = "tool_result",
  ToolProgress = "tool_progress",
  Thinking = "thinking",
  Error = "error",
  Abort = "abort",
  Complete = "complete",
}

export interface StreamEvent {
  type: StreamEventType;
  session_id: string;
  data: string | Record<string, unknown>;
  timestamp: string;
}

export interface SDKExecuteRequest {
  command: string;
  agent_name?: string;
  session_id?: string;
  message?: string;
  config?: AgentConfig;
}

export interface SDKExecuteResponse {
  success: boolean;
  session_id?: string;
  message?: string;
  error?: string;
}

export interface SDKSchema {
  version: string;
  agents: AgentManifest[];
  tools: ToolDefinition[];
  message_types: string[];
  stream_event_types: string[];
}

export type StreamEventHandler = (event: StreamEvent) => void;
