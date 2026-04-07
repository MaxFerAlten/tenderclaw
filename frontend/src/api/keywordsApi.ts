/** Keywords API client. */

export interface KeywordMapping {
  keywords: string[];
  action: string;
  description: string;
  skill: string | null;
}

export interface DetectResult {
  matches: KeywordMapping[];
  primary_action: string | null;
  extracted_task: string;
}

const BASE_URL = "/api/keywords";

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

export const keywordsApi = {
  getMappings(): Promise<KeywordMapping[]> {
    return request(`${BASE_URL}/mappings`);
  },

  detect(text: string): Promise<DetectResult> {
    return request(`${BASE_URL}/detect`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },
};
