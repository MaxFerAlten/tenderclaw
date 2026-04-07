/**
 * TenderClaw Agent SDK - TypeScript Client
 * Type-safe client for TenderClaw SDK operations.
 */

import type {
  AgentManifest,
  SDKExecuteRequest,
  SDKExecuteResponse,
  SDKSchema,
  StreamEvent,
  StreamEventHandler,
  ToolDefinition,
  AgentConfig,
} from "./types";

const BASE_URL = "/api/sdk";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`SDK ${res.status}: ${error}`);
  }

  return res.json();
}

export class SDKClient {
  private ws: WebSocket | null = null;
  private streamHandlers: Set<StreamEventHandler> = new Set();
  private sessionId: string | null = null;

  async listAgents(): Promise<AgentManifest[]> {
    return request<AgentManifest[]>("/agents");
  }

  async getAgent(name: string): Promise<AgentManifest> {
    return request<AgentManifest>(`/agents/${encodeURIComponent(name)}`);
  }

  async listTools(): Promise<ToolDefinition[]> {
    return request<ToolDefinition[]>("/tools");
  }

  async getSchema(): Promise<SDKSchema> {
    return request<SDKSchema>("/schema");
  }

  async execute(req: SDKExecuteRequest): Promise<SDKExecuteResponse> {
    return request<SDKExecuteResponse>("/execute", {
      method: "POST",
      body: JSON.stringify(req),
    });
  }

  async createSession(model?: string): Promise<SDKExecuteResponse> {
    const config: AgentConfig | undefined = model ? { name: "", model } : undefined;
    return this.execute({
      command: "create_session",
      config,
    });
  }

  async sendMessage(
    sessionId: string,
    message: string,
    config?: AgentConfig,
  ): Promise<SDKExecuteResponse> {
    return this.execute({
      command: "send_message",
      session_id: sessionId,
      message,
      config,
    });
  }

  connectStream(sessionId: string): void {
    if (this.ws) {
      this.disconnectStream();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/sdk/stream/${encodeURIComponent(sessionId)}`;

    this.ws = new WebSocket(wsUrl);
    this.sessionId = sessionId;

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as StreamEvent;
        this.streamHandlers.forEach((handler) => handler(data));
      } catch (err) {
        console.error("Failed to parse stream event:", err);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.sessionId = null;
    };
  }

  disconnectStream(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.sessionId = null;
    }
  }

  onStreamEvent(handler: StreamEventHandler): () => void {
    this.streamHandlers.add(handler);
    return () => {
      this.streamHandlers.delete(handler);
    };
  }

  sendStreamMessage(message: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected to stream");
    }

    this.ws.send(
      JSON.stringify({
        type: "send_message",
        message,
      }),
    );
  }

  ping(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "ping" }));
    }
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  get currentSessionId(): string | null {
    return this.sessionId;
  }
}

export const sdk = new SDKClient();

export default sdk;
