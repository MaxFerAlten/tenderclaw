/** Settings Screen — configure providers and model preferences. */

import { useState, useEffect } from "react";
import { Save, Key, Globe, Bot, AlertCircle, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { useSessionStore } from "../../stores/sessionStore";
import { ws } from "../../api/ws";

const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)", color: "bg-orange-500" },
  { id: "openai", name: "OpenAI (GPT)", color: "bg-green-500" },
  { id: "google", name: "Google (Gemini)", color: "bg-blue-500" },
  { id: "xai", name: "xAI (Grok)", color: "bg-purple-500" },
  { id: "deepseek", name: "DeepSeek", color: "bg-cyan-500" },
  { id: "ollama", name: "Ollama (Local)", color: "bg-gray-500" },
  { id: "lmstudio", name: "LM Studio (Local)", color: "bg-amber-600" },
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
  { id: "llama3.1:8b", provider: "ollama", description: "Llama 3.1 8B" },
  { id: "llama3.2:3b", provider: "ollama", description: "Llama 3.2 3B" },
  { id: "qwen2.5:14b", provider: "ollama", description: "Qwen 2.5 14B" },
  { id: "codellama:13b", provider: "ollama", description: "Code Llama 13B" },
];

export function SettingsScreen() {
  const model = useSessionStore((s) => s.model);
  const setModel = useSessionStore((s) => s.setModel);
  const sessionId = useSessionStore((s) => s.sessionId);
  
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    anthropic: "",
    openai: "",
    google: "",
    xai: "",
    deepseek: "",
  });
  const [selectedProvider, setSelectedProvider] = useState("anthropic");
  const [selectedModel, setSelectedModel] = useState(model || "claude-sonnet-4-20250514");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [connectionStatus, setConnectionStatus] = useState<Record<string, "unknown" | "checking" | "ok" | "error">>({});
  const [lmstudioModels, setLmstudioModels] = useState<string[]>([]);
  const [customModelInput, setCustomModelInput] = useState("");

  useEffect(() => {
    // Load saved settings from localStorage
    const savedKeys = localStorage.getItem("tenderclaw_api_keys");
    if (savedKeys) {
      try {
        setApiKeys(JSON.parse(savedKeys));
      } catch {}
    }
    
    // Load saved model
    const savedModel = localStorage.getItem("tenderclaw_model");
    if (savedModel) {
      setSelectedModel(savedModel);
      const provider = POPULAR_MODELS.find(m => m.id === savedModel)?.provider
        ?? (savedModel.includes("/") ? "lmstudio" : "anthropic");
      setSelectedProvider(provider);
      if (provider === "lmstudio") {
        fetchLmstudioModels();
      }
    }
  }, []);

  const fetchLmstudioModels = async (baseUrl?: string) => {
    const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : "";
    try {
      const res = await fetch(`/api/diagnostics/lmstudio/models${params}`);
      if (res.ok) {
        const ids: string[] = await res.json();
        setLmstudioModels(ids);
        if (ids.length > 0 && !ids.includes(selectedModel)) {
          setSelectedModel(ids[0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch LM Studio models:", err);
      setLmstudioModels([]);
    }
  };

  const handleSave = async () => {
    setError("");
    
    // Save API keys and model to localStorage
    localStorage.setItem("tenderclaw_api_keys", JSON.stringify(apiKeys));
    localStorage.setItem("tenderclaw_model", selectedModel);
    
    // Update global model state
    setModel(selectedModel);
    setSelectedProvider(
      POPULAR_MODELS.find(m => m.id === selectedModel)?.provider
        ?? (selectedModel.includes("/") ? "lmstudio" : "anthropic")
    );

    // Push model change to active session via WS + REST
    try {
      // 1. Update session model via WebSocket (instant, no reload needed)
      ws.sendSessionConfig(selectedModel);

      // 2. Persist config on backend (API keys, URLs, session_id)
      await fetch(`/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId ?? undefined,
          ollama_base_url: selectedProvider === "ollama" ? (apiKeys.ollama || "http://localhost:11434") : undefined,
          lmstudio_base_url: selectedProvider === "lmstudio" ? (apiKeys.lmstudio || "http://localhost:1234") : undefined,
          anthropic_api_key: apiKeys.anthropic || undefined,
          openai_api_key: apiKeys.openai || undefined,
          google_api_key: apiKeys.google || undefined,
          xai_api_key: apiKeys.xai || undefined,
          deepseek_api_key: apiKeys.deepseek || undefined,
        }),
      });

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError("Failed to save settings.");
    }
  };

  const filteredModels = POPULAR_MODELS.filter(m => m.provider === selectedProvider);

  return (
    <div className="h-screen bg-zinc-950 text-zinc-100 overflow-y-auto">
      {/* Header con back */}
      <div className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur border-b border-zinc-800 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link 
            to="/" 
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Chat</span>
          </Link>
          <span className="text-sm text-zinc-500">Settings</span>
        </div>
      </div>
      
      <div className="max-w-2xl mx-auto p-8 space-y-8">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Bot className="w-8 h-8 text-blue-400" />
          <h1 className="text-2xl font-bold">TenderClaw Settings</h1>
        </div>

        {/* Provider Selection */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Globe className="w-5 h-5" />
            AI Provider
          </h2>
          
          <div className="grid grid-cols-2 gap-3">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setSelectedProvider(p.id);
                  if (p.id === "lmstudio") {
                    fetchLmstudioModels();
                  } else {
                    const firstModel = POPULAR_MODELS.find(m => m.provider === p.id);
                    if (firstModel) setSelectedModel(firstModel.id);
                  }
                }}
                className={`p-3 rounded-lg border-2 transition-all text-left ${
                  selectedProvider === p.id
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${p.color}`} />
                  <span className="font-medium">{p.name}</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Model Selection */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Bot className="w-5 h-5" />
            Model
          </h2>
          
          <div className="space-y-2">
            {selectedProvider === "lmstudio" ? (
              lmstudioModels.length > 0 ? (
                lmstudioModels.map((id) => (
                  <button
                    key={id}
                    onClick={() => setSelectedModel(id)}
                    className={`w-full p-3 rounded-lg border-2 transition-all text-left ${
                      selectedModel === id
                        ? "border-blue-500 bg-blue-500/10"
                        : "border-zinc-700 hover:border-zinc-600"
                    }`}
                  >
                    <div className="font-mono text-sm">{id}</div>
                  </button>
                ))
              ) : (
                <p className="text-sm text-zinc-500 py-2">
                  No models loaded — test the connection above or enter a model ID manually.
                </p>
              )
            ) : (
              filteredModels.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setSelectedModel(m.id)}
                  className={`w-full p-3 rounded-lg border-2 transition-all text-left ${
                    selectedModel === m.id
                      ? "border-blue-500 bg-blue-500/10"
                      : "border-zinc-700 hover:border-zinc-600"
                  }`}
                >
                  <div className="font-mono text-sm">{m.id}</div>
                  <div className="text-zinc-400 text-sm">{m.description}</div>
                </button>
              ))
            )}
          </div>

          {/* Custom model input — always visible */}
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
                onClick={() => {
                  if (customModelInput.trim()) {
                    setSelectedModel(customModelInput.trim());
                    setCustomModelInput("");
                  }
                }}
                className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm transition-colors"
              >
                Use
              </button>
            </div>
          </div>
          
          <div className="text-sm text-zinc-500">
            Selected: <span className="text-blue-400 font-mono">{selectedModel}</span>
          </div>
        </section>

        {/* API Keys */}
        <section className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Key className="w-5 h-5" />
            API Keys
          </h2>
          
          <p className="text-sm text-zinc-400">
            API keys are stored locally in your browser and sent directly to the server.
            They are never persisted on the server.
          </p>
          
          {PROVIDERS.map((p) => (
            <div key={p.id} className="space-y-1">
              <label className="text-sm font-medium flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${p.color}`} />
                {p.name}
              </label>
              {p.id === "ollama" || p.id === "lmstudio" ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={apiKeys[p.id] || ""}
                    onChange={(e) => setApiKeys({ ...apiKeys, [p.id]: e.target.value })}
                    placeholder={p.id === "ollama" ? "http://localhost:11434" : "http://localhost:1234"}
                    className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500"
                  />
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => {
                        const url = apiKeys[p.id] || (p.id === "ollama" ? "http://localhost:11434" : "http://localhost:1234");
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
                          } else {
                            setConnectionStatus({ ...connectionStatus, [p.id]: "error" });
                          }
                        } catch {
                          setConnectionStatus({ ...connectionStatus, [p.id]: "error" });
                        }
                      }}
                      className="text-xs px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded transition-colors"
                    >
                      Test Connection
                    </button>
                    {connectionStatus[p.id] === "ok" && (
                      <span className="text-xs text-green-400">Connected!</span>
                    )}
                    {connectionStatus[p.id] === "error" && (
                      <span className="text-xs text-red-400">Connection failed</span>
                    )}
                    {connectionStatus[p.id] === "checking" && (
                      <span className="text-xs text-yellow-400">Checking...</span>
                    )}
                  </div>
                </div>
              ) : (
                <input
                  type="password"
                  value={apiKeys[p.id] || ""}
                  onChange={(e) => setApiKeys({ ...apiKeys, [p.id]: e.target.value })}
                  placeholder={`API Key for ${p.name}`}
                  className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500"
                />
              )}
            </div>
          ))}
        </section>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* Save Button */}
        <button
          onClick={handleSave}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors"
        >
          <Save className="w-5 h-5" />
          {saved ? "Saved!" : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
