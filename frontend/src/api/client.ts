/**
 * HTTP client for TenderClaw REST API.
 * All endpoints are relative — Vite proxy handles routing to backend.
 */

const BASE_URL = "/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API ${res.status}: ${error}`);
  }

  return res.json();
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  sessions: {
    list: () => request<{ sessions: unknown[] }>("/sessions"),
    create: (body: { model?: string; working_directory?: string }) =>
      request<{ session_id: string }>("/sessions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: string) => request<unknown>(`/sessions/${id}`),
    delete: (id: string) =>
      request<void>(`/sessions/${id}`, { method: "DELETE" }),
  },

  tools: {
    list: () => request<{ tools: unknown[] }>("/tools"),
  },

  models: {
    list: () => request<{ data: { id: string; owned_by: string }[] }>("/v1/models"),
  },
};
