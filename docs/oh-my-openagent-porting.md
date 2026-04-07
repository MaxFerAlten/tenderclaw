# oh-my-openagent Porting Plan

## Overview

Porting `oh-my-openagent` functionality from OpenCode to TenderClaw.

**Source**: `D:\MY_AI\claude-code\oh-my-openagent\` (OpenCode plugin)
**Target**: `D:\MY_AI\claude-code\TenderClaw\` (TenderClaw)

---

## What is oh-my-openagent

oh-my-openagent is an OpenCode plugin that provides:
- **11 specialized AI agents** for different tasks
- **48 lifecycle hooks** for workflow automation
- **26 tools** for code manipulation
- **Built-in skills** (git-master, playwright, frontend-ui-ux)
- **Commands** (/init-deep, /ralph-loop, /refactor, etc.)
- **MCP integration** (websearch, context7, grep_app)
- **Claude Code compatibility layer**

---

## Architecture Comparison

| Component | oh-my-openagent | TenderClaw Target |
|----------|-----------------|-------------------|
| Agent System | 11 agents in `src/agents/` | Backend orchestration in `backend/orchestration/` |
| Hooks | 48 hooks in `src/hooks/` | Middleware/events system |
| Tools | 26 tools in `src/tools/` | Backend API endpoints |
| Skills | Built-in in `src/features/builtin-skills/` | `skills/` directory |
| Commands | Built-in in `src/features/builtin-commands/` | Skills with slash triggers |
| MCP | Built-in in `src/mcp/` | Backend services |
| Config | JSONC in `oh-my-opencode.jsonc` | Existing config system |

---

## Phase 1: Core Agent System

### 1.1 Agent Definitions

| Agent | Model | Purpose | Priority |
|-------|-------|---------|----------|
| **Sisyphus** | claude-opus-4-6 | Main orchestrator, plans and delegates | HIGH |
| **Hephaestus** | gpt-5.4 | Autonomous deep worker | HIGH |
| **Oracle** | gpt-5.4 | Architecture, review, debugging | HIGH |
| **Librarian** | minimax-m2.7 | Multi-repo analysis, docs | MEDIUM |
| **Explore** | grok-code-fast-1 | Fast codebase grep | MEDIUM |
| **Prometheus** | claude-opus-4-6 | Strategic planner with interview | HIGH |
| **Metis** | claude-opus-4-6 | Plan consultant, pre-planning | MEDIUM |
| **Momus** | gpt-5.4 | Plan reviewer | MEDIUM |
| **Atlas** | claude-sonnet-4-6 | Todo orchestrator | MEDIUM |
| **Multimodal-Looker** | gpt-5.4 | Visual content specialist | LOW |
| **Sisyphus-Junior** | category-dependent | Category-based executor | HIGH |

### 1.2 Agent Files

```
backend/orchestration/
├── agents/
│   ├── __init__.py
│   ├── base.py              # Base agent class
│   ├── sisyphus.py          # Main orchestrator
│   ├── hephaestus.py         # Deep worker
│   ├── oracle.py             # Architecture/review
│   ├── librarian.py          # Docs/code search
│   ├── explore.py            # Fast grep
│   ├── prometheus.py         # Strategic planner
│   ├── metis.py              # Plan consultant
│   ├── momus.py              # Plan reviewer
│   ├── atlas.py              # Todo orchestrator
│   └── multimodal_looker.py  # Visual specialist
├── categories.py             # Category system
└── delegation.py             # Task delegation logic
```

---

## Phase 2: Hook System

### 2.1 Hook Categories

| Category | Count | Description |
|----------|-------|-------------|
| Context & Injection | 6 | AGENTS.md, README.md, rules injection |
| Productivity & Control | 8 | Keywords, think mode, ralph loop |
| Quality & Safety | 5 | Comment checker, edit recovery, hashline |
| Recovery & Stability | 5 | Session recovery, context window, JSON errors |
| Truncation | 1 | Tool output truncation |
| Notifications & UX | 6 | Updates, notifications, reminders |
| Task Management | 5 | Task system integration |
| Continuation | 3 | Todo continuation, unstable agent |

### 2.2 Key Hooks to Port

| Hook | Event | Description | Priority |
|------|-------|-------------|----------|
| **keyword-detector** | Message | Detects ultrawork, search, analyze | HIGH |
| **ralph-loop** | Event | Self-referential loop continuation | HIGH |
| **hashline-edit** | Pre/Post | Hash-anchored edit validation | HIGH |
| **context-injector** | PreTool | AGENTS.md, README injection | HIGH |
| **comment-checker** | PostTool | AI slop comment detection | MEDIUM |
| **session-recovery** | Event | Error recovery | MEDIUM |
| **preemptive-compaction** | Event | Context window management | MEDIUM |

### 2.3 Hook Files

```
backend/hooks/
├── __init__.py
├── registry.py               # Hook registration
├── events.py                 # Event types
├── handlers/
│   ├── keyword_detector.py
│   ├── ralph_loop.py
│   ├── hashline_edit.py
│   ├── context_injector.py
│   ├── comment_checker.py
│   ├── session_recovery.py
│   ├── compaction.py
│   └── ...
└── middleware.py             # Hook execution
```

---

## Phase 3: Tools System

### 3.1 Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| Code Search | grep, glob | Content and file pattern search |
| Edit | hashline-edit | Hash-anchored safe edits |
| LSP | lsp_* | IDE features (rename, goto, refs) |
| AST | ast_grep_* | Pattern-aware search/replace |
| Delegation | task, call_omo_agent | Agent spawning |
| Session | session_* | Session management |
| Skills | skill, skill_mcp | Skill loading |

### 3.2 Key Tools to Port

| Tool | Description | Priority |
|------|-------------|----------|
| **hashline-edit** | Hash-anchored edit with validation | HIGH |
| **lsp_rename** | Workspace rename | HIGH |
| **lsp_goto_definition** | Jump to definition | MEDIUM |
| **lsp_find_references** | Find usages | MEDIUM |
| **ast_grep_search** | AST pattern search | MEDIUM |
| **ast_grep_replace** | AST pattern replace | MEDIUM |
| **delegate-task** | Category-based delegation | HIGH |

### 3.3 Tool Files

```
backend/tools/
├── __init__.py
├── base.py                   # Base tool class
├── registry.py               # Tool registration
├── hashline_edit.py          # Hash-anchored editing
├── lsp/
│   ├── __init__.py
│   ├── rename.py
│   ├── goto_definition.py
│   ├── find_references.py
│   └── diagnostics.py
├── ast_grep/
│   ├── __init__.py
│   ├── search.py
│   └── replace.py
└── session_manager.py        # Session tools
```

---

## Phase 4: Skills System

### 4.1 Built-in Skills

| Skill | Description | Priority |
|-------|-------------|----------|
| **git-master** | Atomic commits, rebase, history | HIGH |
| **playwright** | Browser automation | HIGH |
| **frontend-ui-ux** | Designer-turned-dev | MEDIUM |

### 4.2 Skill Features to Port

- SKILL.md format with YAML frontmatter
- Embedded MCP servers per skill
- Skill loading from paths
- Skill context injection

### 4.3 Skill Files

```
backend/core/
├── skill_loader.py           # Skill loading system
├── skill_registry.py         # Skill registration
└── skill_context.py         # Skill context injection
```

---

## Phase 5: Commands System

### 5.1 Built-in Commands

| Command | Description | Priority |
|---------|-------------|----------|
| **/init-deep** | Generate hierarchical AGENTS.md | HIGH |
| **/ralph-loop** | Self-referential loop | HIGH |
| **/refactor** | Intelligent refactoring | MEDIUM |
| **/start-work** | Execute from Prometheus plan | MEDIUM |
| **/ulw-loop** | Ultrawork loop | HIGH |
| **/handoff** | Create context summary | LOW |

### 5.2 Command Files

```
backend/commands/
├── __init__.py
├── registry.py               # Command registration
├── init_deep.py             # /init-deep
├── ralph_loop.py            # /ralph-loop
├── refactor.py              # /refactor
├── start_work.py            # /start-work
└── handoff.py              # /handoff
```

---

## Phase 6: MCP Integration

### 6.1 Built-in MCPs

| MCP | Description | Priority |
|-----|-------------|----------|
| **websearch** | Exa web search | HIGH |
| **context7** | Official docs lookup | MEDIUM |
| **grep_app** | GitHub code search | MEDIUM |

### 6.2 MCP Features

- Remote HTTP MCP servers
- Skill-embedded MCPs
- OAuth-enabled MCPs
- MCP tool invocation

### 6.3 MCP Files

```
backend/mcp/
├── __init__.py
├── registry.py               # MCP registration
├── server.py                # MCP server base
├── builtin/
│   ├── __init__.py
│   ├── websearch.py         # Exa search
│   ├── context7.py          # Docs lookup
│   └── grep_app.py          # GitHub search
├── oauth.py                 # OAuth handling
└── skill_mcp.py            # Skill-embedded MCP
```

---

## Phase 7: Configuration

### 7.1 Config Features

- JSONC multi-level config (project → user → defaults)
- Zod v4 schema validation
- Config migration
- Legacy config support

### 7.2 Config Files

```
backend/config/
├── __init__.py
├── schema.py                 # Config schema
├── loader.py                # Config loading
├── merger.py                # Deep merge
└── migration.py            # Legacy migration
```

---

## Implementation Checklist

### Phase 1 - Agent System
- [ ] `backend/orchestration/agents/base.py` - Base agent class
- [ ] `backend/orchestration/agents/sisyphus.py` - Main orchestrator
- [ ] `backend/orchestration/agents/prometheus.py` - Strategic planner
- [ ] `backend/orchestration/agents/hephaestus.py` - Deep worker
- [ ] `backend/orchestration/agents/oracle.py` - Review agent
- [ ] `backend/orchestration/agents/explore.py` - Fast grep
- [ ] `backend/orchestration/categories.py` - Category system
- [ ] `backend/orchestration/delegation.py` - Task delegation

### Phase 2 - Hook System
- [ ] `backend/hooks/registry.py` - Hook registration
- [ ] `backend/hooks/handlers/keyword_detector.py` - Keyword detection
- [ ] `backend/hooks/handlers/ralph_loop.py` - Ralph loop
- [ ] `backend/hooks/handlers/hashline_edit.py` - Hash-anchored edit
- [ ] `backend/hooks/handlers/context_injector.py` - Context injection

### Phase 3 - Tools System
- [ ] `backend/tools/hashline_edit.py` - Hash-anchored editing
- [ ] `backend/tools/lsp/` - LSP tools
- [ ] `backend/tools/ast_grep/` - AST tools

### Phase 4 - Skills System
- [ ] `backend/core/skill_loader.py` - Skill loading
- [ ] Update existing skills with MCP support

### Phase 5 - Commands System
- [ ] `backend/commands/registry.py` - Command registration
- [ ] `backend/commands/init_deep.py` - /init-deep
- [ ] `backend/commands/ralph_loop.py` - /ralph-loop

### Phase 6 - MCP Integration
- [ ] `backend/mcp/registry.py` - MCP registration
- [ ] `backend/mcp/builtin/websearch.py` - Web search
- [ ] `backend/mcp/builtin/context7.py` - Docs lookup

### Phase 7 - Configuration
- [ ] `backend/config/schema.py` - Config schema
- [ ] `backend/config/loader.py` - Config loading

---

## File Summary

### Backend Files to Create

| Directory | Files | Description |
|-----------|-------|-------------|
| `backend/orchestration/agents/` | 12 | Agent definitions |
| `backend/hooks/` | 15+ | Hook system |
| `backend/tools/` | 10+ | Tool implementations |
| `backend/commands/` | 8 | Command implementations |
| `backend/mcp/builtin/` | 3 | Built-in MCP servers |
| `backend/config/` | 4 | Configuration system |

**Total new files**: ~50-60

---

## Dependencies

- `zod` (or `pydantic`) for schema validation
- `json5` or custom JSONC parser
- `ast-grep` bindings for AST tools (if available)

---

## Notes

1. **TenderClaw is Python-based** - oh-my-openagent is TypeScript. All code must be ported, not reused.

2. **Agent Model Mapping** - OpenCode uses model identifiers like `claude-opus-4-6`. TenderClaw may use different model names. Agent system should be model-agnostic.

3. **Hooks vs Middleware** - oh-my-openagent hooks are event-based. TenderClaw should implement a similar event/middleware system.

4. **MCP Protocol** - MCP is a standard protocol. Python implementations exist (e.g., `mcp` package).

5. **Hashline Edits** - This is a key innovation. Each line gets a content hash for safe edits. Should be ported as `backend/tools/hashline_edit.py`.

---

## Cronologia Modifiche

| Data | Fase | Descrizione |
|------|------|-------------|
| 2026-04-06 | Piano | Piano creato |
