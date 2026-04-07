/**
 * agentsApi — typed fetch wrappers for /api/agents REST endpoints.
 */

export interface AgentDefinition {
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
  is_builtin?: boolean;
}

export interface AgentPatch {
  description?: string;
  default_model?: string;
  system_prompt?: string;
  tools?: string[];
  enabled?: boolean;
  max_tokens?: number;
}

const BASE = "/api/agents";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const agentsApi = {
  list: (): Promise<AgentDefinition[]> => request(BASE),

  get: (name: string): Promise<AgentDefinition> => request(`${BASE}/${name}`),

  create: (agent: Omit<AgentDefinition, "is_builtin">): Promise<AgentDefinition> =>
    request(BASE, { method: "POST", body: JSON.stringify(agent) }),

  update: (name: string, agent: Omit<AgentDefinition, "is_builtin">): Promise<AgentDefinition> =>
    request(`${BASE}/${name}`, { method: "PUT", body: JSON.stringify(agent) }),

  patch: (name: string, patch: AgentPatch): Promise<AgentDefinition> =>
    request(`${BASE}/${name}`, { method: "PATCH", body: JSON.stringify(patch) }),

  delete: (name: string): Promise<void> =>
    request(`${BASE}/${name}`, { method: "DELETE" }),
};
