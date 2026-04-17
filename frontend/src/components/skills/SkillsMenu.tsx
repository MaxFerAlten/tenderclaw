/** Skills Menu — browse, search, and select skills from the TenderClaw system.
 *
 * Sprint 5: shows auto-selected skill badge when SkillSelector has a match.
 */

import { useState, useEffect, useCallback } from "react";
import { Search, X, Zap, FileText, Play, Loader, AlertCircle, CheckCircle, Sparkles } from "lucide-react";
import { skillsApi, type SkillInfo, type SkillDetail } from "../../api/skillsApi";
import { useSessionStore } from "../../stores/sessionStore";
import { useKeybindingContext } from "../../keybindings";

interface AutoSkillBadgeProps {
  skillName: string;
  confidence: number;
  reason: string;
  onSelect: (name: string) => void;
}

function AutoSkillBadge({ skillName, confidence, reason, onSelect }: AutoSkillBadgeProps) {
  return (
    <button
      onClick={() => onSelect(skillName)}
      title={reason}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/30 hover:bg-violet-500/20 transition-colors text-left"
    >
      <Sparkles className="w-3 h-3 text-violet-400 shrink-0" />
      <span className="text-xs font-medium text-violet-300">{skillName}</span>
      <span className="text-[10px] text-violet-500 ml-1">{Math.round(confidence * 100)}%</span>
    </button>
  );
}

interface SkillsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SkillsMenu({ isOpen, onClose }: SkillsMenuProps) {
  const sessionId = useSessionStore((s) => s.sessionId);
  const { setContext } = useKeybindingContext();

  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [executing, setExecuting] = useState(false);
  const [executeResult, setExecuteResult] = useState<{ success: boolean; message: string } | null>(null);
  const [autoSkill, setAutoSkill] = useState<{ skill_name: string; confidence: number; reason: string } | null>(null);

  useEffect(() => {
    if (isOpen && skills.length === 0) {
      loadSkills();
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      setContext("SkillsMenu");
      return () => setContext("Chat");
    }
  }, [isOpen, setContext]);

  const loadSkills = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await skillsApi.list();
      setSkills(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  };

  const loadSkillDetail = async (name: string) => {
    setLoading(true);
    setError("");
    setExecuteResult(null);
    try {
      const data = await skillsApi.get(name);
      setSelectedSkill(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skill details");
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedSkill) return;
    setExecuting(true);
    setExecuteResult(null);
    try {
      const result = await skillsApi.execute(selectedSkill.name, { session_id: sessionId ?? undefined });
      setExecuteResult({ success: result.success, message: result.message });
    } catch (err) {
      setExecuteResult({ success: false, message: err instanceof Error ? err.message : "Execution failed" });
    } finally {
      setExecuting(false);
    }
  };

  const filteredSkills = skills.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.trigger.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Auto-select skill when search query changes (debounced via useEffect)
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 5) {
      setAutoSkill(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const result = await skillsApi.select(searchQuery);
        const best = result.matches?.[0];
        if (best?.matched) {
          setAutoSkill({ skill_name: best.skill_name, confidence: best.confidence, reason: best.reason });
        } else {
          setAutoSkill(null);
        }
      } catch {
        setAutoSkill(null);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleClose = useCallback(() => {
    setSelectedSkill(null);
    setSearchQuery("");
    setError("");
    setExecuteResult(null);
    onClose();
  }, [onClose]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative w-full max-w-3xl h-[80vh] bg-zinc-900 rounded-xl border border-zinc-700 shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-zinc-800">
          <Zap className="w-6 h-6 text-yellow-400" />
          <h2 className="text-lg font-bold flex-1">Skills Menu</h2>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search + auto-skill badge */}
        <div className="px-6 py-3 border-b border-zinc-800 space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search skills or describe your task..."
              className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          {autoSkill && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Auto-selected:</span>
              <AutoSkillBadge
                skillName={autoSkill.skill_name}
                confidence={autoSkill.confidence}
                reason={autoSkill.reason}
                onSelect={(name) => loadSkillDetail(name)}
              />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Skills List */}
          <div className="w-72 border-r border-zinc-800 overflow-y-auto">
            {loading && skills.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-zinc-500">
                <Loader className="w-5 h-5 animate-spin mr-2" /> Loading...
              </div>
            ) : error && skills.length === 0 ? (
              <div className="p-4 text-red-400 text-sm flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {error}
              </div>
            ) : filteredSkills.length === 0 ? (
              <div className="p-4 text-zinc-500 text-sm">No skills found</div>
            ) : (
              filteredSkills.map((skill) => (
                <button
                  key={skill.name}
                  onClick={() => loadSkillDetail(skill.name)}
                  className={`w-full p-4 text-left border-b border-zinc-800 transition-colors ${
                    selectedSkill?.name === skill.name
                      ? "bg-blue-500/10 border-l-2 border-l-blue-500"
                      : "hover:bg-zinc-800"
                  }`}
                >
                  <div className="font-medium text-sm text-zinc-200">{skill.name}</div>
                  <div className="text-xs text-zinc-500 mt-1 line-clamp-2">{skill.description}</div>
                  {skill.trigger && (
                    <div className="text-xs text-zinc-600 mt-1 font-mono">/{skill.trigger}</div>
                  )}
                </button>
              ))
            )}
          </div>

          {/* Skill Detail */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading && selectedSkill ? (
              <div className="flex items-center justify-center h-32 text-zinc-500">
                <Loader className="w-5 h-5 animate-spin mr-2" /> Loading details...
              </div>
            ) : !selectedSkill ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-500">
                <FileText className="w-12 h-12 mb-3 opacity-30" />
                <p className="text-sm">Select a skill to view details</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Skill Header */}
                <div>
                  <h3 className="text-xl font-bold text-zinc-100">{selectedSkill.name}</h3>
                  {selectedSkill.trigger && (
                    <div className="text-sm text-zinc-400 mt-1 font-mono">/{selectedSkill.trigger}</div>
                  )}
                  <p className="text-sm text-zinc-400 mt-3">{selectedSkill.description}</p>
                </div>

                {/* Agents */}
                {selectedSkill.agents.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-300 mb-2">Compatible Agents</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedSkill.agents.map((agent) => (
                        <span key={agent} className="px-2 py-1 bg-zinc-800 rounded text-xs text-zinc-400">
                          {agent}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Flow */}
                {selectedSkill.flow.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-300 mb-2">Workflow</h4>
                    <ol className="space-y-2">
                      {selectedSkill.flow.map((step, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs flex items-center justify-center">
                            {i + 1}
                          </span>
                          <span className="text-sm text-zinc-400">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Rules */}
                {selectedSkill.rules.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-300 mb-2">Rules</h4>
                    <ul className="space-y-1.5">
                      {selectedSkill.rules.map((rule, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                          <span className="text-zinc-600 mt-1">•</span>
                          {rule}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Execute Result */}
                {executeResult && (
                  <div
                    className={`p-4 rounded-lg flex items-start gap-3 ${
                      executeResult.success ? "bg-green-500/10 border border-green-500/30" : "bg-red-500/10 border border-red-500/30"
                    }`}
                  >
                    {executeResult.success ? (
                      <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    )}
                    <div className="text-sm">{executeResult.message}</div>
                  </div>
                )}

                {/* Execute Button */}
                <div className="pt-4 border-t border-zinc-800">
                  <button
                    onClick={handleExecute}
                    disabled={executing}
                    className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors"
                  >
                    {executing ? (
                      <>
                        <Loader className="w-5 h-5 animate-spin" /> Executing...
                      </>
                    ) : (
                      <>
                        <Play className="w-5 h-5" /> Execute Skill
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
