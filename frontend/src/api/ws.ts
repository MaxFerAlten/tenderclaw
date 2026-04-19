/**
 * WebSocket client for real-time agent communication.
 * Handles connection, reconnection, keepalive, and typed message dispatch.
 */

import type { ChatAttachment, PowerLevel, WSServerEvent } from "./types";

type EventHandler = (event: WSServerEvent) => void;
type StatusHandler = (status: "connecting" | "connected" | "disconnected") => void;

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 10;
const PING_INTERVAL_MS = 15000;

export class TenderClawWS {
  private ws: WebSocket | null = null;
  private sessionId: string = "";
  private handlers: EventHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private reconnectAttempts = 0;
  private shouldReconnect = true;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  connect(sessionId: string): void {
    this.sessionId = sessionId;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this.doConnect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.clearPing();
    this.ws?.close();
    this.ws = null;
  }

  isDisconnected(): boolean {
    return !this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CLOSING;
  }

  send(message: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendUserMessage(content: string, attachments: ChatAttachment[] = [], powerLevel: PowerLevel = "medium"): void {
    this.send({ type: "user_message", content, attachments, power_level: powerLevel });
  }

  sendSessionConfig(model: string): void {
    this.send({ type: "session_config", model });
  }

  sendAbort(): void {
    this.send({ type: "abort", reason: "user_cancelled" });
  }

  sendPermissionResponse(toolUseId: string, decision: "approve" | "deny"): void {
    this.send({ type: "tool_permission_response", tool_use_id: toolUseId, decision });
  }

  onEvent(handler: EventHandler): () => void {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.push(handler);
    return () => {
      this.statusHandlers = this.statusHandlers.filter((h) => h !== handler);
    };
  }

  private clearPing(): void {
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private doConnect(): void {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/api/ws/${this.sessionId}`;

    this.emitStatus("connecting");
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.emitStatus("connected");
      // Keepalive: prevent browser from closing idle WS connections
      this.pingInterval = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    };

    this.ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as WSServerEvent;
        // Session lost (backend restart) — reset store so ChatView creates a new session
        if (event.type === "error" && (event as { code?: string }).code === "session_not_found") {
          this.shouldReconnect = false;
          this.handlers.forEach((h) => h(event));
          this.ws?.close();
          return;
        }
        this.handlers.forEach((h) => h(event));
      } catch {
        console.error("Failed to parse WS message:", ev.data);
      }
    };

    this.ws.onclose = () => {
      this.clearPing();
      this.emitStatus("disconnected");
      if (this.shouldReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        this.reconnectAttempts++;
        setTimeout(() => this.doConnect(), RECONNECT_DELAY_MS * this.reconnectAttempts);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private emitStatus(status: "connecting" | "connected" | "disconnected"): void {
    this.statusHandlers.forEach((h) => h(status));
  }
}

/** Singleton WebSocket instance */
export const ws = new TenderClawWS();
