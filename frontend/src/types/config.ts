/** TenderClaw Configuration Types.

Based on oh-my-openagent's Zod schemas, ported to TypeScript.
Mirrors backend/config/schemas/ directory structure.
 */

export type BuiltinAgentName =
  | "sisyphus"
  | "hephaestus"
  | "prometheus"
  | "oracle"
  | "librarian"
  | "explore"
  | "multimodal-looker"
  | "metis"
  | "momus"
  | "atlas"
  | "sisyphus-junior";

export type BuiltinCategoryName =
  | "visual-engineering"
  | "ultrabrain"
  | "deep"
  | "artistry"
  | "quick"
  | "unspecified-low"
  | "unspecified-high"
  | "writing";

export type BuiltinSkillName =
  | "playwright"
  | "agent-browser"
  | "dev-browser"
  | "frontend-ui-ux"
  | "git-master";

export type ReasoningEffort = "none" | "minimal" | "low" | "medium" | "high" | "xhigh";
export type TextVerbosity = "low" | "medium" | "high";
export type AgentMode = "subagent" | "primary" | "all";
export type NotificationLevel = "off" | "minimal" | "detailed";

export interface ThinkingConfig {
  type: "enabled" | "disabled";
  budgetTokens?: number;
}

export interface AgentPermissionConfig {
  allowBash?: boolean;
  allowWrite?: boolean;
  allowRead?: boolean;
  allowExecute?: boolean;
}

export interface AgentOverrideConfig {
  model?: string;
  fallbackModels?: string[];
  variant?: string;
  category?: string;
  skills?: string[];
  temperature?: number;
  topP?: number;
  prompt?: string;
  promptAppend?: string;
  tools?: Record<string, boolean>;
  disable?: boolean;
  description?: string;
  mode?: AgentMode;
  color?: string;
  permission?: AgentPermissionConfig;
  maxTokens?: number;
  thinking?: ThinkingConfig;
  reasoningEffort?: ReasoningEffort;
  textVerbosity?: TextVerbosity;
  providerOptions?: Record<string, unknown>;
  ultrawork?: { model?: string; variant?: string };
  compaction?: { model?: string; variant?: string };
}

export interface HephaestusOverrideConfig extends AgentOverrideConfig {
  allowNonGptModel?: boolean;
}

export interface AgentOverridesConfig {
  build?: AgentOverrideConfig;
  plan?: AgentOverrideConfig;
  sisyphus?: AgentOverrideConfig;
  hephaestus?: HephaestusOverrideConfig;
  "sisyphus-junior"?: AgentOverrideConfig;
  prometheus?: AgentOverrideConfig;
  metis?: AgentOverrideConfig;
  momus?: AgentOverrideConfig;
  oracle?: AgentOverrideConfig;
  librarian?: AgentOverrideConfig;
  explore?: AgentOverrideConfig;
  "multimodal-looker"?: AgentOverrideConfig;
  atlas?: AgentOverrideConfig;
}

export interface CategoryThinkingConfig {
  type: "enabled" | "disabled";
  budgetTokens?: number;
}

export interface CategoryConfig {
  description?: string;
  model?: string;
  fallbackModels?: string[];
  variant?: string;
  temperature?: number;
  topP?: number;
  maxTokens?: number;
  thinking?: CategoryThinkingConfig;
  reasoningEffort?: ReasoningEffort;
  textVerbosity?: TextVerbosity;
  tools?: Record<string, boolean>;
  promptAppend?: string;
  maxPromptTokens?: number;
  isUnstableAgent?: boolean;
  disable?: boolean;
}

export interface CategoriesConfig {
  "visual-engineering"?: CategoryConfig;
  ultrabrain?: CategoryConfig;
  deep?: CategoryConfig;
  artistry?: CategoryConfig;
  quick?: CategoryConfig;
  "unspecified-low"?: CategoryConfig;
  "unspecified-high"?: CategoryConfig;
  writing?: CategoryConfig;
  [key: string]: CategoryConfig | undefined;
}

export type HookName =
  | "todo-continuation-enforcer"
  | "context-window-monitor"
  | "session-recovery"
  | "session-notification"
  | "comment-checker"
  | "tool-output-truncator"
  | "question-label-truncator"
  | "directory-agents-injector"
  | "directory-readme-injector"
  | "empty-task-response-detector"
  | "think-mode"
  | "model-fallback"
  | "anthropic-context-window-limit-recovery"
  | "preemptive-compaction"
  | "rules-injector"
  | "background-notification"
  | "auto-update-checker"
  | "startup-toast"
  | "keyword-detector"
  | "agent-usage-reminder"
  | "non-interactive-env"
  | "interactive-bash-session"
  | "thinking-block-validator"
  | "ralph-loop"
  | "category-skill-reminder"
  | "compaction-context-injector"
  | "compaction-todo-preserver"
  | "claude-code-hooks"
  | "auto-slash-command"
  | "edit-error-recovery"
  | "json-error-recovery"
  | "delegate-task-retry"
  | "prometheus-md-only"
  | "sisyphus-junior-notepad"
  | "no-sisyphus-gpt"
  | "no-hephaestus-non-gpt"
  | "start-work"
  | "atlas"
  | "unstable-agent-babysitter"
  | "task-resume-info"
  | "stop-continuation-guard"
  | "tasks-todowrite-disabler"
  | "runtime-fallback"
  | "write-existing-file-guard"
  | "bash-file-read-guard"
  | "anthropic-effort"
  | "hashline-read-enhancer"
  | "read-image-resizer"
  | "todo-description-override"
  | "webfetch-redirect-guard"
  | "legacy-plugin-toast";

export interface HookConfig {
  enabled?: boolean;
  priority?: number;
  options?: Record<string, unknown>;
}

export interface HooksConfig {
  [key: string]: HookConfig | undefined;
}

export interface TurnProtectionConfig {
  enabled?: boolean;
  turns?: number;
}

export interface PruningStrategies {
  deduplication?: { enabled?: boolean };
  supersedeWrites?: { enabled?: boolean; aggressive?: boolean };
  purgeErrors?: { enabled?: boolean; turns?: number };
}

export interface DynamicContextPruningConfig {
  enabled?: boolean;
  notification?: NotificationLevel;
  turnProtection?: TurnProtectionConfig;
  protectedTools?: string[];
  strategies?: PruningStrategies;
}

export interface ExperimentalConfig {
  aggressiveTruncation?: boolean;
  autoResume?: boolean;
  preemptiveCompaction?: boolean;
  truncateAllToolOutputs?: boolean;
  dynamicContextPruning?: DynamicContextPruningConfig;
  taskSystem?: boolean;
  pluginLoadTimeoutMs?: number;
  safeHookCreation?: boolean;
  disableOmoEnv?: boolean;
  hashlineEdit?: boolean;
  modelFallbackTitle?: boolean;
  maxTools?: number;
}

export interface SkillDefinition {
  description?: string;
  template?: string;
  from?: string;
  model?: string;
  agent?: string;
  subtask?: boolean;
  argumentHint?: string;
  license?: string;
  compatibility?: string;
  metadata?: Record<string, unknown>;
  allowedTools?: string[];
  disable?: boolean;
}

export type SkillEntry = boolean | SkillDefinition;

export interface SkillsSourcesConfig {
  path: string;
  recursive?: boolean;
  glob?: string;
}

export type SkillSource = string | SkillsSourcesConfig;

export interface SkillsConfig {
  sources?: SkillSource[];
  enable?: string[];
  disable?: string[];
  [key: string]: SkillSource[] | string[] | undefined;
}

export interface GitMasterConfig {
  commitFooter?: boolean | string;
  includeCoAuthoredBy?: boolean;
  gitEnvPrefix?: string;
}

export interface RalphLoopConfig {
  enabled?: boolean;
  defaultMaxIterations?: number;
  stateDir?: string;
  defaultStrategy?: "reset" | "continue";
}

export interface SisyphusTasksConfig {
  storagePath?: string;
  taskListId?: string;
  claudeCodeCompat?: boolean;
}

export interface SisyphusConfig {
  tasks?: SisyphusTasksConfig;
}

export interface CircuitBreakerConfig {
  enabled?: boolean;
  maxToolCalls?: number;
  consecutiveThreshold?: number;
}

export interface BackgroundTaskConfig {
  defaultConcurrency?: number;
  providerConcurrency?: Record<string, number>;
  modelConcurrency?: Record<string, number>;
  maxDepth?: number;
  maxDescendants?: number;
  staleTimeoutMs?: number;
  messageStalenessTimeoutMs?: number;
  taskTtlMs?: number;
  sessionGoneTimeoutMs?: number;
  syncPollTimeoutMs?: number;
  maxToolCalls?: number;
  circuitBreaker?: CircuitBreakerConfig;
}

export interface CommentCheckerConfig {
  customPrompt?: string;
}

export interface RuntimeFallbackConfig {
  enabled?: boolean;
  retryOnErrors?: number[];
  timeoutSeconds?: number;
}

export interface TmuxLayout {
  windowName?: string;
  panes?: Record<string, string>;
}

export interface TmuxConfig {
  enabled?: boolean;
  layout?: TmuxLayout;
}

export interface WebsearchConfig {
  provider?: string;
  apiKey?: string;
}

export interface NotificationConfig {
  enabled?: boolean;
  sound?: boolean;
}

export interface ModelCapabilitiesConfig {
  enabled?: boolean;
  autoRefreshOnStart?: boolean;
  refreshTimeoutMs?: number;
  sourceUrl?: string;
}

export interface BrowserAutomationConfig {
  provider?: "playwright" | "agent-browser" | "playwright-cli";
}

export interface ClaudeCodeConfig {
  enabled?: boolean;
  configPath?: string;
}

export interface StartWorkConfig {
  autoCommit?: boolean;
}

export interface BabysittingConfig {
  enabled?: boolean;
  checkIntervalMs?: number;
}

export interface TenderClawConfig {
  $schema?: string;
  newTaskSystemEnabled?: boolean;
  defaultRunAgent?: string;
  disabledMcps?: string[];
  disabledAgents?: string[];
  disabledSkills?: string[];
  disabledHooks?: string[];
  disabledCommands?: string[];
  disabledTools?: string[];
  hashlineEdit?: boolean;
  modelFallback?: boolean;
  agents?: AgentOverridesConfig;
  categories?: CategoriesConfig;
  claudeCode?: ClaudeCodeConfig;
  commentChecker?: CommentCheckerConfig;
  experimental?: ExperimentalConfig;
  autoUpdate?: boolean;
  skills?: SkillsConfig;
  ralphLoop?: RalphLoopConfig;
  runtimeFallback?: boolean | RuntimeFallbackConfig;
  backgroundTask?: BackgroundTaskConfig;
  notification?: NotificationConfig;
  modelCapabilities?: ModelCapabilitiesConfig;
  babysitting?: BabysittingConfig;
  gitMaster?: GitMasterConfig;
  browserAutomationEngine?: BrowserAutomationConfig;
  websearch?: WebsearchConfig;
  tmux?: TmuxConfig;
  sisyphus?: SisyphusConfig;
  startWork?: StartWorkConfig;
  hooks?: HooksConfig;
  _migrations?: string[];
}

export const BUILTIN_CATEGORIES: CategoriesConfig = {
  "visual-engineering": {
    description: "Frontend, UI/UX, CSS, animations, and visual components",
    model: "claude-sonnet-4-20250514",
    temperature: 0.5,
    reasoningEffort: "medium",
  },
  ultrabrain: {
    description: "Complex reasoning, architecture, deep analysis",
    model: "claude-opus-4-20250514",
    temperature: 0.3,
    reasoningEffort: "high",
    maxTokens: 16384,
  },
  deep: {
    description: "Deep investigation, research, thorough analysis",
    model: "claude-opus-4-20250514",
    temperature: 0.4,
    reasoningEffort: "high",
  },
  artistry: {
    description: "Creative writing, content generation, marketing",
    model: "claude-sonnet-4-20250514",
    temperature: 0.9,
    reasoningEffort: "low",
    textVerbosity: "high",
  },
  quick: {
    description: "Fast, simple tasks, one-liners, small fixes",
    model: "claude-haiku-4-20250707",
    temperature: 0.5,
    reasoningEffort: "none",
    maxTokens: 2048,
  },
  "unspecified-low": {
    description: "Low-priority unspecified tasks",
    model: "claude-haiku-4-20250707",
    temperature: 0.5,
  },
  "unspecified-high": {
    description: "High-priority unspecified tasks",
    model: "claude-sonnet-4-20250514",
    temperature: 0.5,
  },
  writing: {
    description: "Writing, documentation, content creation",
    model: "claude-sonnet-4-20250514",
    temperature: 0.7,
    textVerbosity: "high",
  },
};

export const ALL_HOOK_NAMES: HookName[] = [
  "todo-continuation-enforcer",
  "context-window-monitor",
  "session-recovery",
  "session-notification",
  "comment-checker",
  "tool-output-truncator",
  "question-label-truncator",
  "directory-agents-injector",
  "directory-readme-injector",
  "empty-task-response-detector",
  "think-mode",
  "model-fallback",
  "anthropic-context-window-limit-recovery",
  "preemptive-compaction",
  "rules-injector",
  "background-notification",
  "auto-update-checker",
  "startup-toast",
  "keyword-detector",
  "agent-usage-reminder",
  "non-interactive-env",
  "interactive-bash-session",
  "thinking-block-validator",
  "ralph-loop",
  "category-skill-reminder",
  "compaction-context-injector",
  "compaction-todo-preserver",
  "claude-code-hooks",
  "auto-slash-command",
  "edit-error-recovery",
  "json-error-recovery",
  "delegate-task-retry",
  "prometheus-md-only",
  "sisyphus-junior-notepad",
  "no-sisyphus-gpt",
  "no-hephaestus-non-gpt",
  "start-work",
  "atlas",
  "unstable-agent-babysitter",
  "task-resume-info",
  "stop-continuation-guard",
  "tasks-todowrite-disabler",
  "runtime-fallback",
  "write-existing-file-guard",
  "bash-file-read-guard",
  "anthropic-effort",
  "hashline-read-enhancer",
  "read-image-resizer",
  "todo-description-override",
  "webfetch-redirect-guard",
  "legacy-plugin-toast",
];

export const DEFAULT_GIT_MASTER_CONFIG: GitMasterConfig = {
  commitFooter: true,
  includeCoAuthoredBy: true,
  gitEnvPrefix: "GIT_MASTER=1",
};
