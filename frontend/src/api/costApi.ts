/** Cost API client. */

import type { CostSummary } from "../types/cost";

const BASE_URL = "/api/costs";

export const costApi = {
  async getCurrent(): Promise<CostSummary> {
    const res = await fetch(`${BASE_URL}/current`);
    if (!res.ok) throw new Error(`Failed to fetch cost: ${res.status}`);
    return res.json();
  },

  async getSession(sessionId: string): Promise<CostSummary> {
    const res = await fetch(`${BASE_URL}/session/${sessionId}`);
    if (!res.ok) throw new Error(`Failed to fetch cost: ${res.status}`);
    return res.json();
  },

  async getHistory(): Promise<CostSummary[]> {
    const res = await fetch(`${BASE_URL}/history`);
    if (!res.ok) throw new Error(`Failed to fetch cost history: ${res.status}`);
    return res.json();
  },
};
