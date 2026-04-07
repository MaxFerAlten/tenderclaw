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
};
