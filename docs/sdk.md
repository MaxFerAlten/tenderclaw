# TenderClaw Agent SDK

Programmatic access to TenderClaw agents, tools, and sessions for external integrations.

## Overview

The Agent SDK provides a type-safe interface for:
- Querying available agents and their capabilities
- Executing commands and managing sessions
- Real-time streaming of agent events
- Tool definitions and schema discovery

## Installation

```bash
npm install @tenderclaw/sdk
```

```typescript
import { sdk } from '@tenderclaw/sdk';
// or
import { SDKClient } from '@tenderclaw/sdk';
```

## Quick Start

```typescript
const client = new SDKClient();

// List all available agents
const agents = await client.listAgents();
console.log(agents);

// Create a session
const { session_id } = await client.createSession();

// Connect to stream for real-time events
client.connectStream(session_id);
client.onStreamEvent((event) => {
  console.log(event.type, event.data);
});

// Send a message
await client.sendMessage(session_id, "Hello, agent!");
```

## API Reference

### SDKClient

#### `listAgents(): Promise<AgentManifest[]>`
Returns all available agents.

```typescript
const agents = await sdk.listAgents();
```

#### `getAgent(name: string): Promise<AgentManifest>`
Returns a specific agent by name.

```typescript
const agent = await sdk.getAgent("sisyphus");
```

#### `listTools(): Promise<ToolDefinition[]>`
Returns all available tools.

```typescript
const tools = await sdk.listTools();
```

#### `getSchema(): Promise<SDKSchema>`
Returns the complete SDK schema.

```typescript
const schema = await sdk.getSchema();
console.log(schema.version); // "1.0.0"
```

#### `execute(request: SDKExecuteRequest): Promise<SDKExecuteResponse>`
Execute an SDK command directly.

```typescript
const response = await sdk.execute({
  command: "create_session",
  config: { name: "", model: "claude-sonnet-4-20250514" }
});
```

#### `createSession(model?: string): Promise<SDKExecuteResponse>`
Create a new session.

```typescript
const { session_id } = await sdk.createSession("claude-sonnet-4-20250514");
```

#### `sendMessage(sessionId: string, message: string, config?): Promise<SDKExecuteResponse>`
Send a message to an agent.

```typescript
await sdk.sendMessage(sessionId, "Implement a login feature", {
  model: "claude-sonnet-4-20250514"
});
```

#### Streaming Methods

##### `connectStream(sessionId: string): void`
Connect to the WebSocket stream for a session.

```typescript
sdk.connectStream("my-session-id");
```

##### `disconnectStream(): void`
Disconnect from the stream.

```typescript
sdk.disconnectStream();
```

##### `onStreamEvent(handler: StreamEventHandler): () => void`
Register a handler for stream events. Returns an unsubscribe function.

```typescript
const unsubscribe = sdk.onStreamEvent((event) => {
  switch (event.type) {
    case "delta":
      console.log("Text:", event.data);
      break;
    case "tool_call":
      console.log("Tool:", event.data);
      break;
    case "complete":
      console.log("Done!");
      break;
  }
});

// Later: unsubscribe()
unsubscribe();
```

##### `sendStreamMessage(message: string): void`
Send a message over the stream.

```typescript
sdk.sendStreamMessage("Continue with the implementation");
```

##### `ping(): void`
Send a ping to keep the connection alive.

```typescript
sdk.ping();
```

## Types

### AgentManifest
```typescript
interface AgentManifest {
  name: string;
  description: string;
  mode: "primary" | "subagent";
  default_model: string;
  category: "orchestration" | "exploration" | "advisor" | "specialist" | "utility";
  cost: "free" | "cheap" | "expensive";
  system_prompt: string;
  max_tokens: number;
  tools: string[];
  enabled: boolean;
  is_builtin: boolean;
}
```

### ToolDefinition
```typescript
interface ToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  parameters: ToolParameter[];
  risk_level: "none" | "low" | "medium" | "high";
  is_read_only: boolean;
}
```

### StreamEvent
```typescript
interface StreamEvent {
  type: "delta" | "tool_call" | "tool_result" | "tool_progress" | "thinking" | "error" | "abort" | "complete";
  session_id: string;
  data: string | Record<string, unknown>;
  timestamp: string;
}
```

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sdk/agents` | List all agents |
| GET | `/api/sdk/agents/{name}` | Get agent manifest |
| GET | `/api/sdk/tools` | List all tools |
| POST | `/api/sdk/execute` | Execute SDK command |
| GET | `/api/sdk/schema` | Get SDK schema |
| WS | `/api/sdk/stream/{session_id}` | Stream events |

## Error Handling

```typescript
try {
  const agent = await sdk.getAgent("nonexistent");
} catch (error) {
  if (error instanceof Error) {
    console.error(`SDK Error: ${error.message}`);
  }
}
```

## Examples

### React Integration

```typescript
import { useEffect, useState } from "react";
import { sdk, SDKClient } from "@tenderclaw/sdk";
import type { AgentManifest } from "@tenderclaw/sdk";

function AgentList() {
  const [agents, setAgents] = useState<AgentManifest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sdk.listAgents()
      .then(setAgents)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading agents...</div>;

  return (
    <ul>
      {agents.map((agent) => (
        <li key={agent.name}>
          {agent.name} - {agent.description}
        </li>
      ))}
    </ul>
  );
}
```

### Streaming with React

```typescript
import { useEffect, useState } from "react";
import { sdk } from "@tenderclaw/sdk";
import type { StreamEvent } from "@tenderclaw/sdk";

function AgentStream({ sessionId }: { sessionId: string }) {
  const [events, setEvents] = useState<StreamEvent[]>([]);

  useEffect(() => {
    sdk.connectStream(sessionId);
    
    const unsubscribe = sdk.onStreamEvent((event) => {
      setEvents((prev) => [...prev, event]);
    });

    return () => {
      unsubscribe();
      sdk.disconnectStream();
    };
  }, [sessionId]);

  return (
    <div>
      {events.map((event, i) => (
        <div key={i}>
          [{event.type}] {typeof event.data === "string" ? event.data : JSON.stringify(event.data)}
        </div>
      ))}
    </div>
  );
}
```

### Node.js Usage

```typescript
// Using fetch directly
const response = await fetch("/api/sdk/agents");
const agents = await response.json();

// Or use the SDK client
import { SDKClient } from "@tenderclaw/sdk";

const client = new SDKClient();
const agents = await client.listAgents();
```
