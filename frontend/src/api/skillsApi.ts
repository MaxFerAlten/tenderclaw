/**
 * skillsApi — typed fetch wrappers for /api/skills REST endpoints.
 */

export interface SkillInfo {
  name: string;
  path: string;
  description: string;
  trigger: string;
  agents: string[];
}

export interface SkillDetail extends SkillInfo {
  flow: string[];
  rules: string[];
  raw: string;
}

export interface SkillExecuteRequest {
  session_id?: string;
  params?: Record<string, unknown>;
}

export interface SkillExecuteResponse {
  success: boolean;
  message: string;
  result?: unknown;
}

export interface SkillSelectRequest {
  task: string;
  phase?: string;
  risk?: string;
  limit?: number;
}

export interface SkillSelectMatch {
  skill_name: string;
  confidence: number;
  reason: string;
  phase: string;
  risk: string;
  matched: boolean;
}

export interface SkillSelectResponse {
  matches: SkillSelectMatch[];
  task_snippet: string;
}

export interface SkillTraceItem {
  timestamp: string;
  task_snippet: string;
  phase: string;
  risk: string;
  skill_name: string;
  confidence: number;
  reason: string;
}

const BASE = "/api/skills";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

export const skillsApi = {
  list: (): Promise<SkillInfo[]> => request(BASE),

  get: (name: string): Promise<SkillDetail> => request(`${BASE}/${encodeURIComponent(name)}`),

  execute: (name: string, body?: SkillExecuteRequest): Promise<SkillExecuteResponse> =>
    request(`${BASE}/${encodeURIComponent(name)}/execute`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),

  select: (task: string, opts?: Omit<SkillSelectRequest, "task">): Promise<SkillSelectResponse> =>
    request(`${BASE}/select`, {
      method: "POST",
      body: JSON.stringify({ task, ...opts }),
    }),

  trace: (limit?: number): Promise<SkillTraceItem[]> =>
    request(`${BASE}/trace${limit !== undefined ? `?limit=${limit}` : ""}`),
};
