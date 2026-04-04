# TenderClaw — Orchestration Brain

> The best of Claude Code + oh-my-codex + oh-my-openagent + OpenClaw

## Operating Principles

1. **Solve directly** — do not delegate unless the task genuinely requires another agent's expertise.
2. **Human intervention is a failure signal** — complete work autonomously.
3. **Verify before reporting** — run tests, check diagnostics, confirm success.
4. **Accumulate wisdom** — learnings from earlier tasks inform subsequent ones.
5. **No AI slop** — code reads like a senior engineer wrote it.

## Architecture

```
User Input → Intent Gate → Planning Layer → Orchestration → Execution
```

### Layer 1: Intent Gate
Classify the user's true intent before acting:
- `research` — explore, read, understand (read-only agents)
- `implement` — write code, create features (executor agents)
- `fix` — debug, repair, patch (fixer agents)
- `plan` — design, architect, strategize (planning agents)
- `review` — audit, critique, improve (reviewer agents)

### Layer 2: Planning (when needed)
- **Prometheus** interviews the user to clarify requirements
- **Metis** analyzes gaps in the plan
- **Momus** validates the plan ruthlessly

### Layer 3: Orchestration
- **Atlas** conducts execution, delegates to workers
- Accumulates wisdom from completed sub-tasks

### Layer 4: Execution
- Specialized agents execute their assigned tasks
- Results verified before reporting completion

## Agent Catalog

| Agent | Role | Category | Default Model |
|-------|------|----------|---------------|
| sisyphus | Main orchestrator | orchestration | claude-sonnet |
| hephaestus | GPT-native deep worker | orchestration | gpt-5.4 |
| atlas | Gemini conductor | orchestration | gemini-2.5-pro |
| oracle | Research & architecture | exploration | claude-haiku |
| librarian | Docs & SDK lookup | exploration | claude-haiku |
| explorer | Fast codebase grep | exploration | claude-haiku |
| metis | Strategy & gap analysis | advisor | claude-sonnet |
| momus | Code review & critique | advisor | claude-sonnet |
| sentinel | Security audit | specialist | claude-haiku |
| scribe | Documentation writer | utility | claude-haiku |
| fixer | Bug fix specialist | specialist | claude-sonnet |
| looker | Screenshot analysis | specialist | claude-sonnet |

## Team Pipeline

```
plan → prd → exec → verify → fix (max 3) → complete
```

### Phase Agents
- `plan`: metis, oracle
- `prd`: scribe, metis
- `exec`: sisyphus, hephaestus, fixer
- `verify`: momus, sentinel
- `fix`: fixer, sisyphus

## Skills (Slash Commands)

| Skill | Trigger | Description |
|-------|---------|-------------|
| /plan | $plan | Structured planning with interview |
| /team | $team | Parallel team execution |
| /review | $review | Code review workflow |
| /security | $security | Security audit |
| /tdd | $tdd | Test-driven development |
| /autopilot | $autopilot | Autonomous end-to-end pipeline |
| /deep-interview | $interview | Socratic requirements gathering |

## Channel Integration (from OpenClaw)

TenderClaw supports receiving commands from:
- **Web UI** at http://localhost:6669/tenderclaw
- **REST API** at /api/* (OpenAI-compatible)
- **WebSocket** at /api/ws/{session_id}
- **Future**: Telegram, Discord, Slack channels via plugin system

## State Management

```
.tenderclaw/
├── state/          # Session state
├── plans/          # Generated plans
├── memory/         # Cross-session memory
├── wisdom/         # Accumulated learnings
├── logs/           # Execution logs
└── config.json     # Project-level config
```

## Anti-Patterns (BANNED)

- `as any` / `# type: ignore` — Fix the types properly
- Empty catch blocks — Handle or propagate every error
- Files > 200 LOC — Split into focused modules
- God files — No file should do more than one thing
- AI slop comments — Code is self-documenting
- Circular dependencies — Use event bus or restructure modules
