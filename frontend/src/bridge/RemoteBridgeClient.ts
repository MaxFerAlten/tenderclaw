/** RemoteBridgeClient — client for connecting to TenderClaw remotely. */

export interface BridgeConfig {
  url: string;
  clientId: string;
}

export interface BridgeSession {
  sessionId: string;
  token: string;
  expiresIn: number;
}

export class RemoteBridgeClient {
  private ws: WebSocket | null = null;
  private config: BridgeConfig | null = null;
  private session: BridgeSession | null = null;
  private messageHandlers: Set<(msg: any) => void> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  async connect(config: BridgeConfig): Promise<void> {
    this.config = config;

    const response = await fetch(`${config.url}/api/bridge/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: config.clientId }),
    });

    if (!response.ok) {
      throw new Error("Failed to connect to bridge");
    }

    this.session = await response.json();

    const wsUrl = config.url.replace("http", "ws") + `/api/bridge/ws/${this.session!.sessionId}`;
    this.ws = new WebSocket(wsUrl);

    return new Promise((resolve, reject) => {
      if (!this.ws) return reject(new Error("WebSocket not initialized"));

      this.ws.onopen = () => {
        this.ws!.send(JSON.stringify({ token: this.session!.token }));
      };

      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.status === "authenticated") {
          this.reconnectAttempts = 0;
          resolve();
        } else {
          this.messageHandlers.forEach(h => h(msg));
        }
      };

      this.ws.onerror = () => reject(new Error("WebSocket error"));
      this.ws.onclose = () => this.handleDisconnect();
    });
  }

  private handleDisconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.config) {
      this.reconnectAttempts++;
      setTimeout(() => this.connect(this.config!), 1000 * this.reconnectAttempts);
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  onMessage(handler: (msg: any) => void): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
    this.session = null;
  }
}
