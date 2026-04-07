import { SessionSummary, SessionDetail } from "../types/history";

const API_BASE = "/api/history";

export interface HistoryEntry {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
  last_message: string;
  total_cost_usd: number;
  model: string;
}

export interface HistoryPage {
  entries: HistoryEntry[];
  total: number;
  has_more: boolean;
  cursor: string | null;
}

export interface MessagePage {
  messages: Message[];
  has_more: boolean;
  cursor: string | null;
}

export interface Message {
  role: string;
  content: string | unknown[];
  message_id?: string;
  timestamp?: string;
}

export async function listSessions(params?: {
  limit?: number;
  offset?: number;
  keyword?: string;
  dateFrom?: string;
  dateTo?: string;
}): Promise<{ sessions: SessionSummary[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  if (params?.keyword) searchParams.set("keyword", params.keyword);
  if (params?.dateFrom) searchParams.set("date_from", params.dateFrom);
  if (params?.dateTo) searchParams.set("date_to", params.dateTo);

  const res = await fetch(`${API_BASE}/legacy?${searchParams}`);
  if (!res.ok) throw new Error("Failed to fetch sessions");
  return res.json();
}

export async function getHistory(params: {
  limit?: number;
  before_id?: string;
  search?: string;
}): Promise<HistoryPage> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.before_id) searchParams.set("before_id", params.before_id);
  if (params.search) searchParams.set("search", params.search);

  const res = await fetch(`${API_BASE}?${searchParams}`);
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}

export async function getSessionDetail(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/${sessionId}`);
  if (!res.ok) throw new Error("Failed to fetch session detail");
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/${sessionId}`);
  if (!res.ok) throw new Error("Failed to fetch session");
  return res.json();
}

export async function getSessionMessages(sessionId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/${sessionId}/messages/all`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  return res.json();
}

export async function getMessages(sessionId: string, params?: {
  limit?: number;
  before_id?: string;
}): Promise<MessagePage> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.before_id) searchParams.set("before_id", params.before_id);

  const res = await fetch(`${API_BASE}/${sessionId}/messages?${searchParams}`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete session");
}

export async function exportSession(sessionId: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/export/${sessionId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to export session");
  return res.json();
}

export async function exportAllSessions(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/export-all`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to export all sessions");
  return res.json();
}

export async function importSession(data: unknown): Promise<{ session_id: string }> {
  const res = await fetch(`${API_BASE}/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to import session");
  return res.json();
}
