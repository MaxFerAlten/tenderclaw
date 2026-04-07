/**
 * AgentEditorScreen — view, create, edit, and delete agents.
 *
 * Layout: left panel = agent list grouped by category.
 *         right panel = editor form (read-only for built-ins except safe fields).
 */

import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft, Plus, Trash2, Save, Bot, Lock, RefreshCw,
  ChevronDown, ChevronRight,
} from "lucide-react";
import { agentsApi, type AgentDefinition } from "../../api/agentsApi";
import { useKeybindingContext } from "../../keybindings";

// ── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES = ["orchestration", "exploration", "advisor", "specialist", "utility"] as const;
const CATEGORY_LABELS: Record<string, string> = {
  orchestration: "Orchestration",
  exploration: "Exploration",
  advisor: "Advisor",
  specialist: "Specialist",
  utility: "Utility",
};
const CATEGORY_COLORS: Record<string, string> = {
  orchestration: "text-violet-400",
  exploration: "text-blue-400",
  advisor: "text-amber-400",
  specialist: "text-red-400",
  utility: "text-green-400",
};

const POPULAR_MODELS = [
  "claude-sonnet-4-20250514",
  "claude-opus-4-20250514",
  "claude-haiku-4-20250514",
  "gpt-4o",
  "gpt-4o-mini",
  "gemini-2.5-pro-preview-06-05",
  "gemini-2.0-flash",
  "grok-3",
  "deepseek-chat",
];

const BLANK_AGENT: Omit<AgentDefinition, "is_builtin"> = {
  name: "",
  description: "",
  mode: "subagent",
  default_model: "claude-sonnet-4-20250514",
  category: "utility",
  cost: "cheap",
  system_prompt: "You are a specialized agent for TenderClaw.",
  max_tokens: 16384,
  tools: [],
  enabled: true,
};

// ── Main Component ────────────────────────────────────────────────────────────

export function AgentEditorScreen() {
  const { setContext } = useKeybindingContext();
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [selected, setSelected] = useState<AgentDefinition | null>(null);
  const [form, setForm] = useState<Omit<AgentDefinition, "is_builtin">>(BLANK_AGENT);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setContext("AgentEditor");
    return () => setContext("Chat");
  }, [setContext]);

  const reload = useCallback(async () => {
    try {
      const list = await agentsApi.list();
      setAgents(list);
    } catch (e) {
      setError("Failed to load agents.");
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const selectAgent = (agent: AgentDefinition) => {
    setIsNew(false);
    setSelected(agent);
    setForm({
      name: agent.name,
      description: agent.description,
      mode: agent.mode,
      default_model: agent.default_model,
      category: agent.category,
      cost: agent.cost,
      system_prompt: agent.system_prompt,
      max_tokens: agent.max_tokens,
      tools: agent.tools ?? [],
      enabled: agent.enabled,
    });
    setError("");
    setSaveMsg("");
  };

  const newAgent = () => {
    setIsNew(true);
    setSelected(null);
    setForm({ ...BLANK_AGENT });
    setError("");
    setSaveMsg("");
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError("Name is required."); return; }
    setSaving(true);
    setError("");
    try {
      if (isNew) {
        const created = await agentsApi.create(form);
        await reload();
        selectAgent({ ...created, is_builtin: false });
        setIsNew(false);
      } else if (selected?.is_builtin) {
        // Patch only safe fields for built-ins
        const patched = await agentsApi.patch(form.name, {
          enabled: form.enabled,
          default_model: form.default_model,
          system_prompt: form.system_prompt,
        });
        await reload();
        selectAgent(patched);
      } else {
        const updated = await agentsApi.update(form.name, form);
        await reload();
        selectAgent(updated);
      }
      setSaveMsg("Saved!");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected || selected.is_builtin) return;
    if (!confirm(`Delete agent "${selected.name}"?`)) return;
    try {
      await agentsApi.delete(selected.name);
      setSelected(null);
      setIsNew(false);
      await reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed.");
    }
  };

  const grouped = CATEGORIES.reduce<Record<string, AgentDefinition[]>>((acc, cat) => {
    acc[cat] = agents.filter((a) => a.category === cat);
    return acc;
  }, {} as Record<string, AgentDefinition[]>);

  const isReadOnly = !isNew && !!selected?.is_builtin;

  return (
    <div className="h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top bar */}
      <div className="h-12 border-b border-zinc-800 flex items-center px-4 gap-4 shrink-0">
        <Link
          to="/"
          className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <span className="text-zinc-600">|</span>
        <Bot className="w-5 h-5 text-violet-400" />
        <h1 className="text-sm font-semibold">Agent Editor</h1>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={reload}
            className="p-1.5 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={newAgent}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" /> New Agent
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left panel — agent list ───────────────────────────────── */}
        <aside className="w-56 border-r border-zinc-800 overflow-y-auto shrink-0">
          {CATEGORIES.map((cat) => {
            const items = grouped[cat] ?? [];
            if (items.length === 0) return null;
            const isCollapsed = !!collapsed[cat];
            return (
              <div key={cat}>
                <button
                  className="w-full flex items-center gap-1 px-3 py-1.5 text-xs uppercase tracking-wider text-zinc-500 hover:bg-zinc-900 transition-colors"
                  onClick={() => setCollapsed((c) => ({ ...c, [cat]: !c[cat] }))}
                >
                  {isCollapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  <span className={CATEGORY_COLORS[cat]}>{CATEGORY_LABELS[cat]}</span>
                  <span className="ml-auto">{items.length}</span>
                </button>
                {!isCollapsed && items.map((agent) => (
                  <button
                    key={agent.name}
                    onClick={() => selectAgent(agent)}
                    className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center gap-2 ${
                      selected?.name === agent.name && !isNew
                        ? "bg-zinc-800 text-zinc-100"
                        : "hover:bg-zinc-900 text-zinc-400"
                    }`}
                  >
                    {agent.is_builtin && <Lock className="w-3 h-3 text-zinc-600 shrink-0" />}
                    <span className="truncate">{agent.name}</span>
                    {!agent.enabled && (
                      <span className="ml-auto text-xs text-zinc-600">off</span>
                    )}
                  </button>
                ))}
              </div>
            );
          })}
        </aside>

        {/* ── Right panel — editor ──────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto p-6">
          {!selected && !isNew ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-600 gap-3">
              <Bot className="w-12 h-12" />
              <p>Select an agent or create a new one</p>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto space-y-6">
              {/* Header */}
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold flex-1">
                  {isNew ? "New Agent" : form.name}
                </h2>
                {isReadOnly && (
                  <span className="flex items-center gap-1 text-xs text-zinc-500 bg-zinc-800 px-2 py-1 rounded">
                    <Lock className="w-3 h-3" /> Built-in (partially editable)
                  </span>
                )}
                {!isNew && !selected?.is_builtin && (
                  <button
                    onClick={handleDelete}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-400 px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" /> Delete
                  </button>
                )}
              </div>

              {/* Name (new only) */}
              {isNew && (
                <Field label="Name (slug, lowercase, no spaces)">
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value.toLowerCase().replace(/\s+/g, "_") })}
                    placeholder="my_agent"
                    className={inputCls}
                  />
                </Field>
              )}

              {/* Enabled toggle */}
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  className={`w-10 h-5 rounded-full transition-colors ${form.enabled ? "bg-green-500" : "bg-zinc-700"}`}
                  onClick={() => setForm({ ...form, enabled: !form.enabled })}
                >
                  <div className={`w-4 h-4 bg-white rounded-full mt-0.5 transition-transform ${form.enabled ? "translate-x-5" : "translate-x-0.5"}`} />
                </div>
                <span className="text-sm text-zinc-300">{form.enabled ? "Enabled" : "Disabled"}</span>
              </label>

              {/* Description */}
              <Field label="Description" disabled={isReadOnly && !["enabled", "default_model", "system_prompt"].includes("description")}>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={2}
                  disabled={isReadOnly}
                  className={textareaCls(isReadOnly)}
                  placeholder="What does this agent specialize in?"
                />
              </Field>

              {/* Default model */}
              <Field label="Default Model">
                <select
                  value={form.default_model}
                  onChange={(e) => setForm({ ...form, default_model: e.target.value })}
                  className={inputCls}
                >
                  {POPULAR_MODELS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  {!POPULAR_MODELS.includes(form.default_model) && (
                    <option value={form.default_model}>{form.default_model}</option>
                  )}
                </select>
              </Field>

              {/* Category + Mode + Cost — locked for built-ins */}
              {(!isReadOnly || isNew) && (
                <div className="grid grid-cols-3 gap-4">
                  <Field label="Category">
                    <select
                      value={form.category}
                      onChange={(e) => setForm({ ...form, category: e.target.value as AgentDefinition["category"] })}
                      className={inputCls}
                      disabled={isReadOnly}
                    >
                      {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>)}
                    </select>
                  </Field>
                  <Field label="Mode">
                    <select
                      value={form.mode}
                      onChange={(e) => setForm({ ...form, mode: e.target.value as "primary" | "subagent" })}
                      className={inputCls}
                      disabled={isReadOnly}
                    >
                      <option value="subagent">Subagent</option>
                      <option value="primary">Primary</option>
                    </select>
                  </Field>
                  <Field label="Cost">
                    <select
                      value={form.cost}
                      onChange={(e) => setForm({ ...form, cost: e.target.value as AgentDefinition["cost"] })}
                      className={inputCls}
                      disabled={isReadOnly}
                    >
                      <option value="free">Free</option>
                      <option value="cheap">Cheap</option>
                      <option value="expensive">Expensive</option>
                    </select>
                  </Field>
                </div>
              )}

              {/* System Prompt */}
              <Field label="System Prompt">
                <textarea
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  rows={12}
                  className={`${textareaCls(false)} font-mono text-xs`}
                  placeholder="You are a specialized agent..."
                />
              </Field>

              {/* Tools — locked for built-ins */}
              {!isReadOnly && (
                <Field label="Allowed Tools (comma-separated, empty = all)">
                  <input
                    type="text"
                    value={form.tools.join(", ")}
                    onChange={(e) =>
                      setForm({ ...form, tools: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })
                    }
                    placeholder="Read, Write, Bash, Grep"
                    className={inputCls}
                  />
                </Field>
              )}

              {/* Error */}
              {error && (
                <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded">
                  {error}
                </p>
              )}

              {/* Save button */}
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded font-semibold flex items-center justify-center gap-2 transition-colors"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving…" : saveMsg || "Save"}
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const inputCls =
  "w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500 disabled:opacity-50 disabled:cursor-not-allowed";

const textareaCls = (disabled: boolean) =>
  `w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500 resize-y ${
    disabled ? "opacity-50 cursor-not-allowed" : ""
  }`;

function Field({
  label,
  children,
  disabled,
}: {
  label: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1">
      <label className={`text-sm font-medium ${disabled ? "text-zinc-600" : "text-zinc-300"}`}>
        {label}
      </label>
      {children}
    </div>
  );
}
