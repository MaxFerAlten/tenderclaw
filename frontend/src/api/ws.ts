/**
 * WebSocket client for real-time agent communication.
 * Handles connection, reconnection, and typed message dispatch.
 */

import type { WSServerEvent } from "./types";

type EventHandler = (event: WSServerEvent) => void;
type StatusHandler = (status: "connecting" | "connected" | "disconnected") => void;

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 10;

export class TenderClawWS {
  private ws: WebSocket | null = null;
  private sessionId: string = "";
  private handlers: EventHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private reconnectAttempts = 0;
  private shouldReconnect = true;

  connect(sessionId: string): void {
    this.sessionId = sessionId;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this.doConnect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.ws?.close();
    this.ws = null;
  }

  send(message: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendUserMessage(content: string): void {
    this.send({ type: "user_message", content });
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

  private doConnect(): void {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/api/ws/${this.sessionId}`;

    this.emitStatus("connecting");
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.emitStatus("connected");
    };

    this.ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as WSServerEvent;
        this.handlers.forEach((h) => h(event));
      } catch {
        console.error("Failed to parse WS message:", ev.data);
      }
    };

    this.ws.onclose = () => {
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
