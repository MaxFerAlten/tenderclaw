/**
 * Notification store (Zustand) — manages real-time HUD notifications.
 * Handles toast queue, auto-dismiss timers, and notification history.
 */

import { create } from "zustand";

export interface HUDNotification {
  id: string;
  level: "info" | "success" | "warning" | "error";
  category: "agent" | "tool" | "pipeline" | "system" | "security";
  title: string;
  body: string;
  agentName?: string;
  autoDismissMs: number;
  timestamp: number;
  dismissed: boolean;
}

export interface ThinkingState {
  agentName: string;
  phase: string;
  progressPct: number;
  detail: string;
  active: boolean;
}

interface NotificationStore {
  notifications: HUDNotification[];
  thinking: ThinkingState | null;
  unreadCount: number;
  showPanel: boolean;

  addNotification: (n: Omit<HUDNotification, "timestamp" | "dismissed">) => void;
  dismissNotification: (id: string) => void;
  dismissAll: () => void;
  clearAll: () => void;
  setThinking: (thinking: ThinkingState | null) => void;
  togglePanel: () => void;
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  thinking: null,
  unreadCount: 0,
  showPanel: false,

  addNotification: (n) => {
    const notification: HUDNotification = {
      ...n,
      timestamp: Date.now(),
      dismissed: false,
    };

    set((s) => ({
      notifications: [notification, ...s.notifications].slice(0, 100),
      unreadCount: s.unreadCount + 1,
    }));

    if (n.autoDismissMs > 0) {
      setTimeout(() => {
        get().dismissNotification(n.id);
      }, n.autoDismissMs);
    }
  },

  dismissNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, dismissed: true } : n
      ),
    })),

  dismissAll: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, dismissed: true })),
      unreadCount: 0,
    })),

  clearAll: () => set({ notifications: [], unreadCount: 0 }),

  setThinking: (thinking) => set({ thinking }),

  togglePanel: () =>
    set((s) => ({
      showPanel: !s.showPanel,
      unreadCount: s.showPanel ? s.unreadCount : 0,
    })),
}));
