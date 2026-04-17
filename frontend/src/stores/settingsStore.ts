/**
 * settingsStore — Zustand store for application settings.
 * Decoupled from sessionStore to keep concerns separate.
 */

import { create } from "zustand";

export interface ProviderStatus {
  keySet: boolean;
  validated: boolean;
  error: string;
}

interface SettingsStore {
  // Per-provider status (populated from /api/config/status)
  providerStatus: Record<string, ProviderStatus>;
  // Currently selected default model
  defaultModel: string;
  // Loading states
  validating: Record<string, boolean>;

  // Actions
  loadStatus: () => Promise<void>;
  validateProvider: (provider: string, apiKey?: string) => Promise<boolean>;
  setDefaultModel: (model: string) => void;
  resetKeys: () => Promise<void>;
}

const PROVIDER_IDS = ["anthropic", "openai", "google", "xai", "deepseek", "openrouter", "opencode", "ollama", "lmstudio", "llamacpp"];

export const useSettingsStore = create<SettingsStore>((set, _get) => ({
  providerStatus: Object.fromEntries(
    PROVIDER_IDS.map((p) => [p, { keySet: false, validated: false, error: "" }])
  ),
  defaultModel: localStorage.getItem("tenderclaw_model") ?? "claude-sonnet-4-20250514",
  validating: {},

  loadStatus: async () => {
    try {
      const res = await fetch("/api/config/status");
      if (!res.ok) return;
      const data: Record<string, { configured: boolean; validated: boolean; error?: string }> =
        await res.json();
      set({
        providerStatus: Object.fromEntries(
          Object.entries(data).map(([p, s]) => [
            p,
            { keySet: s.configured, validated: s.validated, error: s.error ?? "" },
          ])
        ),
      });
    } catch {
      // ignore network errors silently
    }
  },

  validateProvider: async (provider: string, _apiKey?: string) => {
    set((s) => ({ validating: { ...s.validating, [provider]: true } }));
    try {
      const res = await fetch(`/api/config/validate/${provider}`, { method: "PATCH" });
      const data = await res.json();
      const ok = res.ok && data.ok === true;
      set((s) => ({
        validating: { ...s.validating, [provider]: false },
        providerStatus: {
          ...s.providerStatus,
          [provider]: {
            keySet: true,
            validated: ok,
            error: ok ? "" : (data.error ?? "Validation failed"),
          },
        },
      }));
      return ok;
    } catch {
      set((s) => ({
        validating: { ...s.validating, [provider]: false },
        providerStatus: {
          ...s.providerStatus,
          [provider]: { keySet: false, validated: false, error: "Network error" },
        },
      }));
      return false;
    }
  },

  setDefaultModel: (model) => {
    localStorage.setItem("tenderclaw_model", model);
    set({ defaultModel: model });
  },

  resetKeys: async () => {
    localStorage.removeItem("tenderclaw_api_keys");
    localStorage.removeItem("tenderclaw_model");
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        anthropic_api_key: "",
        openai_api_key: "",
        google_api_key: "",
        xai_api_key: "",
        deepseek_api_key: "",
      }),
    }).catch(() => {});
    set({
      providerStatus: Object.fromEntries(
        PROVIDER_IDS.map((p) => [p, { keySet: false, validated: false, error: "" }])
      ),
    });
  },
}));
