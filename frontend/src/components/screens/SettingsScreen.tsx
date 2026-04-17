/** Settings Screen — configure providers, model, keys, and danger zone. */

import { useState, useEffect } from "react";
import { Save, Key, Globe, Bot, AlertCircle, ArrowLeft, CheckCircle, XCircle, Loader, DollarSign } from "lucide-react";
import { Link } from "react-router-dom";
import { useSessionStore } from "../../stores/sessionStore";
import { useSettingsStore } from "../../stores/settingsStore";
import { useKeybindingContext } from "../../keybindings";
import { ProviderStatusBadge } from "../shared/ProviderStatusBadge";
import { ws } from "../../api/ws";
import { costApi } from "../../api/costApi";
import type { CostSummary } from "../../types/cost";

const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)", color: "bg-orange-500" },
  { id: "openai", name: "OpenAI (GPT)", color: "bg-green-500" },
  { id: "google", name: "Google (Gemini)", color: "bg-blue-500" },
  { id: "xai", name: "xAI (Grok)", color: "bg-purple-500" },
  { id: "deepseek", name: "DeepSeek", color: "bg-cyan-500" },
  { id: "openrouter", name: "OpenRouter", color: "bg-indigo-500" },
  { id: "opencode", name: "OpenCode", color: "bg-red-500" },
  { id: "ollama", name: "Ollama (Local)", color: "bg-gray-500" },
  { id: "lmstudio", name: "LM Studio (Local)", color: "bg-amber-600" },
  { id: "llamacpp", name: "llama.cpp (Local)", color: "bg-teal-500" },
  { id: "gpt4free", name: "gpt4free (Free)", color: "bg-pink-500" },
];

const POPULAR_MODELS = [
  { id: "claude-sonnet-4-20250514", provider: "anthropic", description: "Claude Sonnet 4 - Latest" },
  { id: "claude-opus-4-20250514", provider: "anthropic", description: "Claude Opus 4 - Most capable" },
  { id: "claude-haiku-4-20250514", provider: "anthropic", description: "Claude Haiku 4 - Fast & cheap" },
  { id: "gpt-4o", provider: "openai", description: "GPT-4o - Multimodal" },
  { id: "gpt-4o-mini", provider: "openai", description: "GPT-4o mini - Fast" },
  { id: "gemini-2.5-pro-preview-06-05", provider: "google", description: "Gemini 2.5 Pro" },
  { id: "gemini-2.0-flash", provider: "google", description: "Gemini 2.0 Flash" },
  { id: "grok-3", provider: "xai", description: "Grok 3" },
  { id: "deepseek-chat", provider: "deepseek", description: "DeepSeek Chat" },
  { id: "anthropic/claude-3.5-sonnet", provider: "openrouter", description: "Claude 3.5 Sonnet (OR)" },
  { id: "anthropic/claude-3-haiku", provider: "openrouter", description: "Claude 3 Haiku (OR)" },
  { id: "openai/gpt-4o", provider: "openrouter", description: "GPT-4o (OR)" },
  { id: "openai/gpt-4o-mini", provider: "openrouter", description: "GPT-4o mini (OR)" },
  { id: "meta-llama/llama-3.1-70b-instruct", provider: "openrouter", description: "Llama 3.1 70B (OR)" },
  { id: "mistralai/mistral-7b-instruct", provider: "openrouter", description: "Mistral 7B (OR)" },
  { id: "qwen3.6-plus-free", provider: "opencode", description: "Qwen 3.6 Plus - Free" },
  { id: "gpt-5.4-mini", provider: "opencode", description: "GPT-5.4 Mini" },
  { id: "claude-sonnet-4-6", provider: "opencode", description: "Claude Sonnet 4.6" },
  { id: "minimax-m2.5-free", provider: "opencode", description: "MiniMax M2.5 - Free" },
  { id: "nemotron-3-super-free", provider: "opencode", description: "Nemotron 3 - Free" },
  { id: "llama3.1:8b", provider: "ollama", description: "Llama 3.1 8B" },
  { id: "llama3.2:3b", provider: "ollama", description: "Llama 3.2 3B" },
  { id: "qwen2.5:14b", provider: "ollama", description: "Qwen 2.5 14B" },
  { id: "codellama:13b", provider: "ollama", description: "Code Llama 13B" },
];

export function SettingsScreen() {
  const model = useSessionStore((s) => s.model);
  const setModel = useSessionStore((s) => s.setModel);
  const sessionId = useSessionStore((s) => s.sessionId);
  const { setContext } = useKeybindingContext();

  const { providerStatus, loadStatus, validateProvider, resetKeys } = useSettingsStore();

  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    anthropic: "", openai: "", google: "", xai: "", deepseek: "", openrouter: "", opencode: "",
    ollama: "", lmstudio: "", llamacpp: "",
  });
  const [selectedProvider, setSelectedProvider] = useState("anthropic");
  const [selectedModel, setSelectedModel] = useState(model || "claude-sonnet-4-20250514");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [connectionStatus, setConnectionStatus] = useState<Record<string, "unknown" | "checking" | "ok" | "error">>({});
  const [lmstudioModels, setLmstudioModels] = useState<string[]>([]);
  const [llamacppModels, setLlamacppModels] = useState<string[]>([]);
  const [gpt4freeModels, setGpt4freeModels] = useState<string[]>([]);
  const [openrouterModels, setOpenrouterModels] = useState<string[]>([]);
  const [opencodeModels, setOpencodeModels] = useState<string[]>([]);
  const [customModelInput, setCustomModelInput] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [inlineValidation, setInlineValidation] = useState<Record<string, "idle" | "checking" | "ok" | "error">>({});
  const [costHistory, setCostHistory] = useState<CostSummary[]>([]);
  const [costLoading, setCostLoading] = useState(true);

  useEffect(() => {
    const savedKeys = localStorage.getItem("tenderclaw_api_keys");
    if (savedKeys) {
      try { setApiKeys(JSON.parse(savedKeys)); } catch {}
    }
    const savedModel = localStorage.getItem("tenderclaw_model");
    const savedProvider = localStorage.getItem("tenderclaw_provider");
    if (savedModel) {
      setSelectedModel(savedModel);
      const provider = savedProvider
        ?? POPULAR_MODELS.find((m) => m.id === savedModel)?.provider
        ?? (savedModel.includes("/") ? "openrouter" : "anthropic");
      setSelectedProvider(provider);
      if (provider === "lmstudio") fetchLmstudioModels();
      if (provider === "llamacpp") fetchLlamacppModels();
      if (provider === "openrouter") fetchOpenrouterModels();
      if (provider === "opencode") fetchOpencodeModels();
      if (provider === "gpt4free") fetchGpt4freeModels();
    }
    loadStatus();
    costApi.getHistory()
      .then(setCostHistory)
      .catch(() => {})
      .finally(() => setCostLoading(false));
  }, [loadStatus]);

  useEffect(() => {
    setContext("Settings");
    return () => setContext("Chat");
  }, [setContext]);

  // Hydrate settings from the backend's /api/config — the server is the source
  // of truth for `selected_provider` and local base URLs after a reload. We
  // only overwrite fields the server knows about, leaving cloud API keys
  // (which live in localStorage) untouched.
  useEffect(() => {
    const url = sessionId
      ? `/api/config?session_id=${encodeURIComponent(sessionId)}`
      : "/api/config";
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => {
        if (!cfg) return;
        if (cfg.selected_provider) {
          setSelectedProvider(cfg.selected_provider);
          // Kick off model list fetches for providers that load dynamically.
          if (cfg.selected_provider === "lmstudio") fetchLmstudioModels(cfg.lmstudio_base_url || undefined);
          else if (cfg.selected_provider === "llamacpp") fetchLlamacppModels(cfg.llamacpp_base_url || undefined);
          else if (cfg.selected_provider === "gpt4free") fetchGpt4freeModels(cfg.gpt4free_base_url || undefined);
          else if (cfg.selected_provider === "openrouter") fetchOpenrouterModels();
          else if (cfg.selected_provider === "opencode") fetchOpencodeModels();
        }
        // Merge local base URLs into the `apiKeys` record used by the form.
        // Only fill fields that are currently empty — user edits win.
        setApiKeys((prev) => ({
          ...prev,
          ollama: prev.ollama || cfg.ollama_base_url || "",
          lmstudio: prev.lmstudio || cfg.lmstudio_base_url || "",
          llamacpp: prev.llamacpp || cfg.llamacpp_base_url || "",
          gpt4free: prev.gpt4free || cfg.gpt4free_base_url || "",
        }));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const fetchLmstudioModels = async (baseUrl?: string) => {
    const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : "";
    try {
      const res = await fetch(`/api/diagnostics/lmstudio/models${params}`);
      if (res.ok) {
        const ids: string[] = await res.json();
        setLmstudioModels(ids);
        if (ids.length > 0 && !ids.includes(selectedModel)) setSelectedModel(ids[0]);
      }
    } catch { setLmstudioModels([]); }
  };

  const fetchOpenrouterModels = async () => {
    try {
      const res = await fetch("/api/diagnostics/openrouter/models");
      if (res.ok) {
        const ids: string[] = await res.json();
        setOpenrouterModels(ids);
      }
    } catch { setOpenrouterModels([]); }
  };

  const fetchOpencodeModels = async () => {
    try {
      const res = await fetch("/api/diagnostics/opencode/models");
      if (res.ok) {
        const ids: string[] = await res.json();
        setOpencodeModels(ids);
      }
    } catch { setOpencodeModels([]); }
  };

  const fetchGpt4freeModels = async (baseUrl?: string) => {
    const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : "";
    try {
      const res = await fetch(`/api/diagnostics/gpt4free/models${params}`);
      if (res.ok) {
        const ids: string[] = await res.json();
        setGpt4freeModels(ids);
        if (ids.length > 0 && !ids.includes(selectedModel)) setSelectedModel(ids[0]);
      }
    } catch { setGpt4freeModels([]); }
  };

  const fetchLlamacppModels = async (baseUrl?: string) => {
    const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : "";
    try {
      const res = await fetch(`/api/diagnostics/llamacpp/models${params}`);
      if (res.ok) {
        const ids: string[] = await res.json();
        setLlamacppModels(ids);
        if (ids.length > 0 && !ids.includes(selectedModel)) setSelectedModel(ids[0]);
      }
    } catch { setLlamacppModels([]); }
  };

  const handleTestCloudProvider = async (providerId: string) => {
    // Save key to backend first
    const body: Record<string, string> = {};
    const keyMap: Record<string, string> = {
      anthropic: "anthropic_api_key",
      openai: "openai_api_key",
      google: "google_api_key",
      xai: "xai_api_key",
      deepseek: "deepseek_api_key",
      openrouter: "openrouter_api_key",
      opencode: "opencode_api_key",
    };
    if (keyMap[providerId]) body[keyMap[providerId]] = apiKeys[providerId] ?? "";

    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, session_id: sessionId ?? undefined }),
    });

    setInlineValidation((v) => ({ ...v, [providerId]: "checking" }));
    const ok = await validateProvider(providerId);
    setInlineValidation((v) => ({ ...v, [providerId]: ok ? "ok" : "error" }));
    if (ok && providerId === "opencode") fetchOpencodeModels();
    if (ok && providerId === "openrouter") fetchOpenrouterModels();
    setTimeout(() => setInlineValidation((v) => ({ ...v, [providerId]: "idle" })), 4000);
  };

  const handleSave = async () => {
    setError("");
    localStorage.setItem("tenderclaw_api_keys", JSON.stringify(apiKeys));
    localStorage.setItem("tenderclaw_model", selectedModel);
    localStorage.setItem("tenderclaw_provider", selectedProvider);
    setModel(selectedModel);
    try {
      ws.sendSessionConfig(selectedModel);
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId ?? undefined,
          ollama_base_url: apiKeys.ollama || undefined,
          lmstudio_base_url: apiKeys.lmstudio || undefined,
          llamacpp_base_url: apiKeys.llamacpp || undefined,
          gpt4free_base_url: apiKeys.gpt4free || undefined,
          anthropic_api_key: apiKeys.anthropic || undefined,
          openai_api_key: apiKeys.openai || undefined,
          google_api_key: apiKeys.google || undefined,
          xai_api_key: apiKeys.xai || undefined,
          deepseek_api_key: apiKeys.deepseek || undefined,
          openrouter_api_key: apiKeys.openrouter || undefined,
          opencode_api_key: apiKeys.opencode || undefined,
          selected_provider: selectedProvider,
        }),
      });
      setSaved(true);
      const currentProvider = POPULAR_MODELS.find((m) => m.id === selectedModel)?.provider
        ?? (selectedModel.includes("/") ? "openrouter" : "anthropic");
      if (currentProvider === "openrouter") fetchOpenrouterModels();
      if (currentProvider === "opencode") fetchOpencodeModels();
      setTimeout(() => { setSaved(false); loadStatus(); }, 2000);
    } catch { setError("Failed to save settings."); }
  };

  const handleReset = async () => {
    await resetKeys();
    setApiKeys({ anthropic: "", openai: "", google: "", xai: "", deepseek: "", openrouter: "", opencode: "" });
    setShowResetConfirm(false);
  };

  const filteredModels = POPULAR_MODELS.filter((m) => m.provider === selectedProvider);
  const cloudProviders = PROVIDERS.filter((p) => p.id !== "ollama" && p.id !== "lmstudio");
  const localProviders = PROVIDERS.filter((p) => p.id === "ollama" || p.id === "lmstudio" || p.id === "llamacpp" || p.id === "gpt4free");

  return (
    <div className="h-screen bg-zinc-950 text-zinc-100 overflow-y-auto">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur border-b border-zinc-800 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 transition-colors">
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Chat</span>
          </Link>
          <span className="text-sm text-zinc-500">Settings</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-8 space-y-8">
        <div className="flex items-center gap-3">
          <Bot className="w-8 h-8 text-blue-400" />
          <h1 className="text-2xl font-bold">TenderClaw Settings</h1>
        </div>

        {/* ── Provider Selection ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Globe className="w-5 h-5" /> AI Provider
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {PROVIDERS.map((p) => {
              const status = providerStatus[p.id];
              return (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedProvider(p.id);
                    if (p.id === "lmstudio") fetchLmstudioModels();
                    else if (p.id === "llamacpp") fetchLlamacppModels();
                    else if (p.id === "openrouter") fetchOpenrouterModels();
                    else if (p.id === "opencode") fetchOpencodeModels();
                    else if (p.id === "gpt4free") fetchGpt4freeModels();
                    else {
                      const first = POPULAR_MODELS.find((m) => m.provider === p.id);
                      if (first) setSelectedModel(first.id);
                    }
                  }}
                  className={`p-3 rounded-lg border-2 transition-all text-left ${
                    selectedProvider === p.id ? "border-blue-500 bg-blue-500/10" : "border-zinc-700 hover:border-zinc-600"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full ${p.color}`} />
                    <span className="font-medium flex-1">{p.name}</span>
                    {status && (
                      <ProviderStatusBadge
                        keySet={status.keySet}
                        validated={status.validated}
                        error={status.error}
                      />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* ── Model Selection ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Bot className="w-5 h-5" /> Model
          </h2>
          <div className="space-y-2">
            {selectedProvider === "lmstudio" ? (
              lmstudioModels.length > 0 ? (
                lmstudioModels.map((id) => (
                  <ModelButton key={id} id={id} label={id} selected={selectedModel === id} onClick={() => setSelectedModel(id)} />
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  No models loaded — test the connection below or enter a model ID manually.
                </p>
              )
            ) : selectedProvider === "openrouter" ? (
              openrouterModels.length > 0 ? (
                openrouterModels.slice(0, 50).map((id) => (
                  <ModelButton key={id} id={id} label={id} selected={selectedModel === id} onClick={() => setSelectedModel(id)} />
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  Enter a model ID manually (e.g. anthropic/claude-3.5-sonnet)
                </p>
              )
            ) : selectedProvider === "opencode" ? (
              opencodeModels.length > 0 ? (
                opencodeModels.map((id) => (
                  <ModelButton key={id} id={id} label={id} selected={selectedModel === id} onClick={() => setSelectedModel(id)} />
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  No models loaded — test the connection below or enter a model ID manually.
                </p>
              )
            ) : selectedProvider === "llamacpp" ? (
              llamacppModels.length > 0 ? (
                llamacppModels.map((id) => (
                  <ModelButton key={id} id={id} label={id} selected={selectedModel === id} onClick={() => setSelectedModel(id)} />
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  No models loaded — test the connection below or enter a model ID manually.
                </p>
              )
            ) : selectedProvider === "gpt4free" ? (
              gpt4freeModels.length > 0 ? (
                gpt4freeModels.map((id) => (
                  <ModelButton key={id} id={id} label={id} selected={selectedModel === id} onClick={() => setSelectedModel(id)} />
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  No models loaded — start gpt4free at http://localhost:1337 and test the connection.
                </p>
              )
            ) : (
              filteredModels.map((m) => (
                <ModelButton key={m.id} id={m.id} label={m.id} description={m.description} selected={selectedModel === m.id} onClick={() => setSelectedModel(m.id)} />
              ))
            )}
          </div>
          <div className="space-y-1 pt-2 border-t border-zinc-800">
            <label className="text-sm text-zinc-400">Or type a model ID manually</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customModelInput}
                onChange={(e) => setCustomModelInput(e.target.value)}
                placeholder="e.g. unsloth/qwen3.5-9b"
                className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={() => { if (customModelInput.trim()) { setSelectedModel(customModelInput.trim()); setCustomModelInput(""); } }}
                className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm transition-colors"
              >Use</button>
            </div>
          </div>
          <div className="text-sm text-zinc-500">
            Selected: <span className="text-blue-400 font-mono">{selectedModel}</span>
          </div>
        </section>

        {/* ── Cloud API Keys ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Key className="w-5 h-5" /> Cloud API Keys
          </h2>
          <p className="text-sm text-zinc-400">
            Keys are stored in your browser and sent to the server per session. They are never persisted server-side.
          </p>
          {cloudProviders.map((p) => {
            const status = providerStatus[p.id];
            const iv = inlineValidation[p.id] ?? "idle";
            return (
              <div key={p.id} className="space-y-1.5">
                <label className="text-sm font-medium flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${p.color}`} />
                  {p.name}
                  {status && (
                    <ProviderStatusBadge keySet={status.keySet} validated={status.validated} error={status.error} />
                  )}
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeys[p.id] || ""}
                    onChange={(e) => setApiKeys({ ...apiKeys, [p.id]: e.target.value })}
                    placeholder={`API Key for ${p.name}`}
                    className="flex-1 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={() => handleTestCloudProvider(p.id)}
                    disabled={iv === "checking" || !apiKeys[p.id]}
                    className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 rounded-lg text-xs transition-colors whitespace-nowrap flex items-center gap-1"
                  >
                    {iv === "checking" ? (
                      <><Loader className="w-3 h-3 animate-spin" /> Testing…</>
                    ) : iv === "ok" ? (
                      <><CheckCircle className="w-3 h-3 text-green-400" /> OK</>
                    ) : iv === "error" ? (
                      <><XCircle className="w-3 h-3 text-red-400" /> Failed</>
                    ) : "Test Key"}
                  </button>
                </div>
                {status?.error && (
                  <p className="text-xs text-red-400">{status.error}</p>
                )}
              </div>
            );
          })}
        </section>

        {/* ── Local Providers ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Local Providers</h2>
          {localProviders.map((p) => (
            <div key={p.id} className="space-y-1">
              <label className="text-sm font-medium flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${p.color}`} />
                {p.name}
              </label>
              <div className="space-y-2">
                <input
                  type="text"
                  value={apiKeys[p.id] || ""}
                  onChange={(e) => setApiKeys({ ...apiKeys, [p.id]: e.target.value })}
                  placeholder={p.id === "ollama" ? "http://localhost:11434" : p.id === "lmstudio" ? "http://localhost:1234" : p.id === "gpt4free" ? "http://localhost:1337" : "http://localhost:3080"}
                  className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={async () => {
                      const url = apiKeys[p.id] || (p.id === "ollama" ? "http://localhost:11434" : p.id === "lmstudio" ? "http://localhost:1234" : p.id === "gpt4free" ? "http://localhost:1337" : "http://localhost:3080");
                      setConnectionStatus({ ...connectionStatus, [p.id]: "checking" });
                      try {
                        const endpoint = p.id === "lmstudio"
                          ? `/api/diagnostics/lmstudio?base_url=${encodeURIComponent(url)}`
                          : `/api/diagnostics/${p.id}?base_url=${encodeURIComponent(url)}`;
                        const res = await fetch(endpoint);
                        const data = await res.json();
                        if (res.ok && data.status === "ok") {
                          setConnectionStatus({ ...connectionStatus, [p.id]: "ok" });
                          if (p.id === "lmstudio") fetchLmstudioModels(url);
                          else if (p.id === "gpt4free") fetchGpt4freeModels(url);
                          else if (p.id === "llamacpp") fetchLlamacppModels(url);
                        } else {
                          setConnectionStatus({ ...connectionStatus, [p.id]: "error" });
                        }
                      } catch {
                        setConnectionStatus({ ...connectionStatus, [p.id]: "error" });
                      }
                    }}
                    className="text-xs px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded transition-colors"
                  >Test Connection</button>
                  {connectionStatus[p.id] === "ok" && <span className="text-xs text-green-400">Connected!</span>}
                  {connectionStatus[p.id] === "error" && <span className="text-xs text-red-400">Connection failed</span>}
                  {connectionStatus[p.id] === "checking" && <span className="text-xs text-yellow-400">Checking…</span>}
                </div>
              </div>
            </div>
          ))}
        </section>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
            <AlertCircle className="w-5 h-5" /> {error}
          </div>
        )}

        {/* Save */}
        <button
          onClick={handleSave}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors"
        >
          <Save className="w-5 h-5" />
          {saved ? "Saved!" : "Save Settings"}
        </button>

        {/* ── Session Costs ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <DollarSign className="w-5 h-5" /> Session Costs
          </h2>
          {costLoading ? (
            <p className="text-sm text-zinc-500">Loading...</p>
          ) : costHistory.length === 0 ? (
            <p className="text-sm text-zinc-500">No session costs available.</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {costHistory.slice(0, 20).map((session) => (
                <div key={session.session_id} className="flex justify-between items-center p-2 bg-zinc-800 rounded text-sm">
                  <span className="text-zinc-400 font-mono text-xs truncate max-w-48" title={session.session_id}>
                    {session.session_id.slice(0, 8)}...
                  </span>
                  <span className="text-emerald-400 font-mono">
                    ${session.total_cost_usd.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── Danger Zone ── */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4 border border-red-900/30">
          <h2 className="text-lg font-semibold text-red-400">Danger Zone</h2>
          <p className="text-sm text-zinc-400">
            Permanently clear all stored API keys and reset settings to defaults.
          </p>
          {!showResetConfirm ? (
            <button
              onClick={() => setShowResetConfirm(true)}
              className="px-4 py-2 border border-red-700 text-red-400 hover:bg-red-900/20 rounded-lg text-sm transition-colors"
            >
              Reset All Keys
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <span className="text-sm text-zinc-300">Are you sure?</span>
              <button
                onClick={handleReset}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-semibold transition-colors"
              >Confirm Reset</button>
              <button
                onClick={() => setShowResetConfirm(false)}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm transition-colors"
              >Cancel</button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ModelButton({
  label, description, selected, onClick,
}: { id?: string; label: string; description?: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full p-3 rounded-lg border-2 transition-all text-left ${
        selected ? "border-blue-500 bg-blue-500/10" : "border-zinc-700 hover:border-zinc-600"
      }`}
    >
      <div className="font-mono text-sm">{label}</div>
      {description && <div className="text-zinc-400 text-sm">{description}</div>}
    </button>
  );
}
