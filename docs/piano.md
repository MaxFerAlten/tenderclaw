# TenderClaw Porting Plan

## Overview

Piano di porting delle feature mancanti da `claude-code` a `TenderClaw`, organizzato in fasi per priorità e interdipendenze.

**Riferimento**: `D:\MY_AI\claude-code\claude-code\` (originale)
**Target**: `D:\MY_AI\claude-code\TenderClaw\` (porting)

---

## Fase 1: Core Utilities ✅ COMPLETATA

### 1.1 Settings Migrations System
**Complessità**: LOW | **Dipendenze**: Nessuna

Sistema per migrare settings tra versioni (es. cambio nome config, rinominare API keys).

**File creati**:
```
backend/migrations/
├── __init__.py
├── registry.py          # Registro migrations con MigrationRegistry
├── runner.py            # Esegue migrations pendenti
└── migrations/
    ├── __init__.py     # Auto-discovery delle migrations
    └── 001_migrate_legacy_settings.py

backend/api/migrations_api.py
backend/tests/test_migrations.py
```

**API endpoints**:
- `GET /api/migrations/status` - Mostra migrations applicate
- `POST /api/migrations/run` - Forza esecuzione migrations

**Features**:
- Run automatico all'avvio
- Tracking in `global_config`
- Idempotenti (safe to run multiple times)
- 8 test pytest

---

### 1.2 Enhanced Usage Tracker
**Complessità**: MEDIUM | **Dipendenze**: Nessuna

Estende il tracker esistente per tracciare costi per modello, persistenza sessioni, token dettagliati.

**File creati/modificati**:
```
backend/runtime/usage_tracker.py  # ESPANSO
backend/services/cost_tracker.py # NUOVO
backend/api/cost_api.py         # NUOVO
backend/tests/test_usage_tracker.py
```

**Features aggiunte**:
```python
# Track per-model
model_usage: dict[str, ModelUsage]

# Persistence
save_to_disk()
load_from_disk()

# Metrics integration (OpenTelemetry)
record_to_metrics()

# ModelUsage TypedDict
- input_tokens
- output_tokens  
- cache_read_input_tokens
- cache_creation_input_tokens
- web_search_requests
- cost_usd
- context_window
- max_output_tokens
- api_duration_ms
```

**API endpoints**:
- `GET /api/costs/current` - Costi sessione corrente
- `GET /api/costs/session/{id}` - Costi specifica sessione
- `GET /api/costs/history` - Storico costi per sessione

**11 test pytest**

---

### 1.3 Cost Display UI
**Complessità**: LOW | **Dipendenze**: 1.2

Mostra costi sessione nel frontend.

**File creati**:
```
frontend/src/types/cost.ts
frontend/src/components/shared/CostBadge.tsx
frontend/src/api/costApi.ts
```

**Features**:
- Badge nel header con costo totale (compact mode)
- Tooltip con breakdown per modello
- Storico sessioni in Settings
- Refresh automatico ogni 30 secondi

**Integrazione**:
- Header.tsx - CostBadge in compact mode
- SettingsScreen.tsx - Sezione "Session Costs" con storico

---

## Fase 2: Keybindings System ✅ COMPLETATA

### 2.1 Keybindings Parser & Resolver
**Complessità**: HIGH | **Dipendenze**: Nessuna

Sistema di keyboard shortcuts completo con parsing, risoluzione, contesti.

**File creati**:
```
frontend/src/keybindings/
├── types.ts              # Tipi TypeScript
├── parser.ts             # Parse "ctrl+shift+k" -> keystroke
├── resolver.ts           # Mappa keypress -> action
├── defaultBindings.ts    # 30+ default bindings
├── KeybindingContext.tsx # React Context provider
├── useKeybinding.ts      # Hook per componenti
└── index.ts             # Esport

backend/api/keybindings_api.py
```

**Tipi**:
```typescript
type ParsedKeystroke = {
  key: string
  ctrl: boolean
  alt: boolean
  shift: boolean
  meta: boolean
  super: boolean
}

type Chord = ParsedKeystroke[]

type ParsedBinding = {
  chord: Chord
  action: string
  context: KeybindingContextName
}

type KeybindingContextName = 
  | "Global" | "Chat" | "Settings" | "HistorySearch"
  | "HistoryDetail" | "Canvas" | "AgentEditor"
  | "SkillsMenu" | "PromptInput"
```

**API endpoints**:
- `GET /api/keybindings/defaults` - Binding di default
- `GET /api/keybindings/actions` - Tutte le azioni disponibili
- `GET /api/keybindings/status` - Status binding

---

### 2.2 Keybindings Integration
**Complessità**: MEDIUM | **Dipendenze**: 2.1

Integra keybindings nel frontend.

**Componenti modificati**:
```
frontend/src/App.tsx              # Wrappa con KeybindingProvider
frontend/src/components/
├── chat/ChatView.tsx             # Chat bindings
├── screens/SettingsScreen.tsx    # Settings bindings
├── screens/HistoryScreen.tsx     # History bindings
├── screens/AgentEditorScreen.tsx # Agent editor bindings
├── skills/SkillsMenu.tsx       # Skills bindings
└── shared/KeyboardShortcutsHelp.tsx  # Modal help (NUOVO)
frontend/src/components/layout/
├── Sidebar.tsx                  # Toggle button
├── Header.tsx                   # Toggle button
└── AppShell.tsx                 # Supporto props
```

**Azioni supportate**:
```
Global:      escape, ctrl+shift+p, ctrl+/, ctrl+b, ctrl+k
Chat:        enter, shift+enter, ctrl+enter, ctrl+up/down, ctrl+l
Settings:    escape, tab, shift+tab
History:     escape, enter, ctrl+f, j, k
AgentEditor: ctrl+s, ctrl+n, ctrl+d, delete, escape
Canvas:      ctrl+=, ctrl+-, ctrl+0, f
SkillsMenu:  escape, enter, j, k, /
```

**Global shortcuts**:
- `Ctrl+B` - Toggle sidebar
- `Ctrl+/` - Show keyboard shortcuts help

---

## Fase 3: Session Management ✅ COMPLETATA

### 3.1 Extended History API with Pagination
**Complessità**: MEDIUM | **Dipendenze**: Nessuna

API per fetch e gestione storico sessioni con pagination.

**File modificati**:
```
backend/services/history_service.py  # ESPANSO
backend/api/history_api.py          # ESPANSO
backend/tests/test_history.py      # NUOVO
```

**Nuovi metodi**:
```python
get_sessions(limit, before_id, search)  # Cursor-based paging
get_session_detail(session_id)
get_session_messages(session_id, limit, before_id)
delete_session(session_id)
export_session(session_id)
```

**Nuovi endpoint API**:
| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/history?limit=&before_id=&search=` | Lista paginata |
| `GET /api/history/{id}` | Dettaglio sessione |
| `GET /api/history/{id}/messages` | Messaggi paginati |
| `DELETE /api/history/{id}` | Elimina sessione |
| `GET /api/history/{id}/export` | Esporta JSON |

---

### 3.2 HistoryDetailScreen Component
**Complessità**: MEDIUM | **Dipendenze**: 3.1

**File creati**:
```
frontend/src/components/screens/HistoryDetailScreen.tsx
```

**Features**:
- Vista dettaglio sessione singola
- Lista messaggi con pagination (load more)
- Export sessione come JSON
- Delete con conferma
- Badge per role (user/assistant)
- Timestamp per ogni messaggio
- Link copy per messaggi

**Integrazione**:
- App.tsx - Route `/history/:sessionId`
- HistoryScreen.tsx - Click naviga a detail screen

---

## Fase 4: Advanced Features ✅ COMPLETATA

### 4.1 Vim Mode
**Complessità**: HIGH | **Dipendenze**: Nessuna

Modal editing style Vim nel prompt input.

**File creati**:
```
frontend/src/vim/
├── types.ts              # VimMode, VimState, VimMotion, VimOperator
├── modes.ts              # Normal, Insert, Visual, Command transitions
├── motions.ts            # h,j,k,l,w,b,e,0,^,$,gg,G
├── operators.ts          # d,y,c,x,p
├── VimInput.tsx          # Componente input vim-style
└── index.ts

backend/utils/vim_motions.py
backend/utils/vim_operators.py
backend/tests/test_vim.py
```

**Modalità supportate**:
- Normal mode
- Insert mode
- Visual mode
- Command mode

**Motions**:
`h`, `l` (char), `w`, `b`, `e` (word), `0`, `^`, `$` (line), `gg`, `G` (file)

**Operators**:
`d` (delete), `y` (yank), `c` (change), `x` (delete char), `p` (put)

**10 test pytest**

---

### 4.2 Buddy Companion
**Complessità**: MEDIUM | **Dipendenze**: Nessuna

Pet companion con sprite animations per engagement.

**File creati**:
```
frontend/src/components/buddy/
├── types.ts               # Buddy, BuddyStats, BuddyNotification
├── BuddySprite.tsx       # Sprite animation component
├── BuddyPanel.tsx        # Pannello stats e achievements
└── index.ts

backend/services/buddy_service.py
```

**Buddy features**:
```typescript
interface Buddy {
  id: string
  name: string
  species: "cat" | "dog" | "rabbit" | "owl" | "dragon"
  rarity: "common" | "rare" | "epic" | "legendary"
  stats: { xp, level, happiness, energy }
  mood: "happy" | "neutral" | "thinking" | "sleeping"
  accessory: string | null
}
```

**BuddyService methods**:
- `generate_buddy()` - Genera buddy casuale
- `get_buddy(user_id)` - Get or create buddy
- `add_xp(user_id, amount)` - Aggiunge XP con level up
- `update_mood(user_id, mood)` - Aggiorna mood

**Integrazione**:
- Sidebar.tsx - Pulsante "Companion"
- App.tsx - BuddyPanel con stato

---

### 4.3 Coordinator Mode
**Complessità**: MEDIUM | **Dipendenze**: Agent system

Gestione multi-task per coordinamento agent.

**File creati**:
```
backend/orchestration/coordinator.py
backend/api/coordinator_api.py
frontend/src/components/screens/CoordinatorScreen.tsx
```

**Coordinator features**:
```python
@dataclass
class Coordinator:
    id: str
    name: str
    state: CoordinatorState  # IDLE, ORCHESTRATING, PAUSED
    tasks: list[Task]
    agents: dict[str, str]   # agent_id -> session_id
    results: dict[str, str]  # task_id -> result

@dataclass
class Task:
    id: str
    description: str
    status: "pending" | "running" | "completed" | "failed"
    assignee: str | None
    result: str | None
```

**CoordinatorManager methods**:
- `create(name)` - Crea nuovo coordinator
- `get(coordinator_id)` - Get coordinator
- `list_all()` - Lista tutti
- `delete(coordinator_id)` - Elimina

**API endpoints**:
- `POST /api/coordinator` - Crea coordinator
- `GET /api/coordinator` - Lista coordinators
- `GET /api/coordinator/{id}` - Dettagli
- `POST /api/coordinator/{id}/tasks` - Aggiungi task
- `POST /api/coordinator/{id}/tasks/{task_id}/assign` - Assegna
- `POST /api/coordinator/{id}/tasks/{task_id}/complete` - Completa
- `DELETE /api/coordinator/{id}` - Elimina

**Integrazione**:
- Sidebar.tsx - Link "Coordinators"
- App.tsx - Route `/coordinator`

---

## Fase 5: Future ✅ COMPLETATA

### 5.1 Remote Bridge
**Complessità**: HIGH | **Dipendenze**: WebSocket system

Full remote bridge con JWT auth, trusted device.

**File creati**:
```
backend/bridge/remote_bridge.py
backend/api/bridge_api.py
frontend/src/bridge/
├── RemoteBridgeClient.ts
└── index.ts
```

**RemoteBridge features**:
```python
@dataclass
class RemoteSession:
    id: str
    bridge_id: str
    client_id: str
    state: BridgeState  # DISCONNECTED, CONNECTING, CONNECTED, AUTHENTICATED
    created_at: datetime
    last_activity: datetime
    metadata: dict

class BridgeConfig:
    host: str = "0.0.0.0"
    port: int = 7001
    jwt_secret: str
    jwt_expiry_hours: int = 24
    max_sessions: int = 10
    heartbeat_interval: int = 30
```

**RemoteBridge methods**:
- `generate_token(session_id, client_id)` - JWT token
- `verify_token(token)` - Verifica token
- `connect(client_id)` - Crea sessione
- `authenticate(session_id, token)` - Auth
- `disconnect(session_id)` - Disconnetti
- `cleanup_stale_sessions(timeout)` - Cleanup

**API endpoints**:
- `POST /api/bridge/connect` - Connetti
- `GET /api/bridge/status` - Status
- `GET /api/bridge/sessions` - Lista sessioni
- `DELETE /api/bridge/sessions/{id}` - Disconnetti
- `WS /api/bridge/ws/{session_id}` - WebSocket

**Dipendenze**: `PyJWT>=2.8.0`

---

### 5.2 Voice Mode
**Complessità**: HIGH | **Dipendenze**: Browser Web Speech API

Speech-to-text streaming nel browser.

**File creati**:
```
frontend/src/components/voice/
├── types.ts              # VoiceConfig, VoiceState, VoiceTranscript
├── useVoiceMode.ts       # Hook React per Web Speech API
├── VoiceButton.tsx       # Pulsante microfono
├── VoiceInput.tsx        # Input con supporto vocale
└── index.ts
```

**useVoiceMode features**:
```typescript
interface VoiceConfig {
  enabled: boolean
  continuous: boolean
  interimResults: boolean
  lang: string
}

type VoiceState = "idle" | "listening" | "processing"

interface VoiceTranscript {
  final: string
  interim?: string
  timestamp: number
}
```

**Hook returns**:
- `state` - VoiceState attuale
- `transcripts` - Lista trascrizioni
- `isSupported` - Check browser support
- `isListening` - Boolean
- `startListening()` / `stopListening()` / `toggleListening()`
- `getFinalTranscript()` - Combina trascrizioni finali

**VoiceButton props**:
- size: "sm" | "md" | "lg"
- Animazione pulse quando listening
- Icone Mic/MicOff

**Integrazione**:
- PromptInput.tsx - VoiceButton affianco textarea
- Browser Web Speech API (SpeechRecognition)

---

### 5.3 Analytics / Datadog
**Complessità**: HIGH | **Dipendenze**: OpenTelemetry (già implementato)

Feature flags, event logging, Datadog integration.

**File creati**:
```
backend/services/analytics/
├── __init__.py
├── datadog.py             # DatadogLogger
├── first_party.py         # FirstPartyEventLogger
├── growthbook.py          # FeatureFlagSystem
└── (implicit __init__)

backend/api/analytics_api.py
```

**DatadogLogger**:
```python
class DatadogLogger:
    def log(message, level, tags, **extra) -> bool
    def log_event(event_name, properties, tags) -> bool
```

**FirstPartyEventLogger** (privacy-first):
```python
class FirstPartyEventLogger:
    def log(event_name, properties, user_id, session_id) -> Event
    def get_events(date, event_name, limit) -> list[Event]
```

**FeatureFlagSystem**:
```python
class FeatureFlagSystem:
    def get(name, default) -> bool
    def set(name, enabled, value)
    def on_change(listener)
    def is_enabled(feature) -> bool
```

**Predefined flags**:
- FEATURE_VOICE_MODE
- FEATURE_BUDDY_COMPANION
- FEATURE_REMOTE_BRIDGE
- FEATURE_VIM_MODE
- FEATURE_ADVANCED_ANALYTICS

**API endpoints**:
- `POST /api/analytics/event` - Log evento
- `GET /api/analytics/events` - Get eventi
- `GET /api/analytics/flags` - Get tutti i flag
- `GET /api/analytics/flags/{name}` - Get flag specifico
- `POST /api/analytics/flags/{name}` - Set flag

---

## Implementation Checklist

### Fase 1 - Core Utilities
- [x] `backend/migrations/` - Sistema migrations
- [x] `backend/services/cost_tracker.py` - Tracker esteso
- [x] `frontend/src/components/shared/CostBadge.tsx` - UI costi
- [x] API: `/api/costs/*`, `/api/migrations/*`

### Fase 2 - Keybindings
- [x] `frontend/src/keybindings/` - Sistema completo
- [x] `backend/api/keybindings_api.py` - Backend API
- [x] Integrazione in App.tsx e components
- [x] 30+ binding actions

### Fase 3 - Session Management
- [x] `backend/api/history_api.py` - API estesa con pagination
- [x] `frontend/src/components/screens/HistoryDetailScreen.tsx` - Vista dettaglio

### Fase 4 - Advanced Features
- [x] `frontend/src/vim/` - Vim mode
- [x] `frontend/src/components/buddy/` - Buddy companion
- [x] `backend/orchestration/coordinator.py` - Coordinator

### Fase 5 - Future
- [x] Remote Bridge
- [x] Voice Mode
- [x] Analytics

---

## File Summary

### Backend Files Created/Modified
| Directory | Files | Description |
|-----------|-------|-------------|
| `backend/migrations/` | 4 | Settings migrations system |
| `backend/runtime/` | 1 mod | Enhanced usage tracker |
| `backend/services/` | 2 | Cost tracker, Buddy service |
| `backend/api/` | 10+ | Migrations, Costs, Keybindings, History, Coordinator, Bridge, Analytics, Ralph, Keywords, Modes |
| `backend/bridge/` | 1 | Remote bridge system |
| `backend/orchestration/` | 1 | Coordinator mode |
| `backend/utils/` | 2 | Vim motions/operators |
| `backend/core/` | 3 | Keyword detection, Modes, Ralph state |
| `backend/tests/` | 6 | Test files |

### Frontend Files Created/Modified
| Directory | Files | Description |
|-----------|-------|-------------|
| `frontend/src/keybindings/` | 7 | Keybindings system |
| `frontend/src/vim/` | 6 | Vim mode |
| `frontend/src/components/buddy/` | 4 | Buddy companion |
| `frontend/src/components/voice/` | 5 | Voice mode |
| `frontend/src/components/screens/` | 2 | Coordinator, HistoryDetail |
| `frontend/src/bridge/` | 2 | Remote bridge client |
| `frontend/src/types/` | 1 | Cost types |
| `frontend/src/api/` | 3 | Cost, Keywords APIs |

### Skills Ported (21 total)
- `ralph/`, `team/`, `analyze/`, `plan/`, `tdd/`
- `code-review/`, `cancel/`, `ultraqa/`, `security-review/`
- `autopilot/`, `deep-interview/`, `doctor/`, `git-master/`
- `visual-verdict/`, `web-clone/`, `ecomode/`, `deepsearch/`
- `swarm/`, `ultrawork/`, `worker/`, `trace/`

**Total new files**: ~70+
**Total tests**: 38 pytest

---

## Note

1. **Priorità**: Tutte le fasi completate.

2. **Test**: Ogni fase include test pytest.

3. **Build Status**:
   - Frontend: ✅ OK (1686 modules)
   - Backend: ✅ OK
   - Tests: 35 passed, 3 skipped

4. **Breaking Changes**: Nessuno.

---

## Cronologia Modifiche

| Data | Fase | Descrizione |
|------|------|-------------|
| 2026-04-05 | - | Piano creato |
| 2026-04-05 | Fase 1 | Completata: Migrations + Usage Tracker + Cost UI |
| 2026-04-05 | Fase 2 | Completata: Keybindings System + Integration |
| 2026-04-05 | Fase 3 | Completata: History API paginata + Detail screen |
| 2026-04-05 | Fase 4 | Completata: Vim Mode + Buddy Companion + Coordinator |
| 2026-04-05 | Fase 5 | Completata: Remote Bridge + Voice Mode + Analytics |
| 2026-04-06 | oh-my-codex | Completato: ralph, team, keyword detection |
| 2026-04-06 | oh-my-codex | Completato: analyze, plan, tdd, code-review, cancel, ultraqa, security-review |
| 2026-04-06 | oh-my-codex | Completato: autopilot, deep-interview, doctor, git-master |
| 2026-04-06 | oh-my-codex | Completato: visual-verdict, web-clone, ecomode, deepsearch, swarm, ultrawork, worker, trace |

---

## TODO (Future Enhancements)

- [ ] MCP Client full implementation
- [ ] Enhanced MCP UI (MCPConnectionManager.tsx)
- [ ] Vim mode integration in PromptInput
- [ ] Buddy XP persistence to backend
- [ ] Remote bridge WebSocket server startup
- [ ] Voice mode server-side processing
- [ ] Datadog API key configuration
- [ ] Analytics dashboard UI

---

## oh-my-codex Porting (Bonus)

### Feature portate da oh-my-codex

| Feature | Source | Status |
|---------|--------|--------|
| **$ralph** | skills/ralph/ | ✅ Completato |
| **$team** | skills/team/ | ✅ Completato |
| **Keyword Detection** | Sistema automatico | ✅ Completato |
| **$analyze** | skills/analyze/ | ✅ Completato |
| **$plan** | skills/plan/ | ✅ Completato |
| **$tdd** | skills/tdd/ | ✅ Completato |
| **$code-review** | skills/code-review/ | ✅ Completato |
| **$cancel** | skills/cancel/ | ✅ Completato |
| **$ultraqa** | skills/ultraqa/ | ✅ Completato |
| **$security-review** | skills/security-review/ | ✅ Completato |
| **Mode Management** | backend/core/modes.py | ✅ Completato |

### Remaining oh-my-codex skills to port

| Skill | Description | Status |
|-------|-------------|--------|
| $autopilot | Full autonomous end-to-end execution | ✅ Completato |
| $deep-interview | Socratic requirements clarification | ✅ Completato |
| $doctor | Diagnose and fix issues | ✅ Completato |
| $git-master | Git expert operations | ✅ Completato |
| $visual-verdict | Visual QA comparison | ✅ Completato |
| $web-clone | Website cloning | ✅ Completato |
| $ecomode | Token-efficient routing | ✅ Completato |
| $deepsearch | Thorough codebase search | ✅ Completato |
| $swarm | Swarm coordination (alias for team) | ✅ Completato |
| $ultrawork | Parallel execution engine | ✅ Completato |
| $worker | Team worker protocol | ✅ Completato |
| $trace | Execution trace display | ✅ Completato |

### $ralph Skill
**Files creati:**
```
skills/ralph/SKILL.md      # Metadata
skills/ralph/RALPH.md       # Execution prompt
backend/core/ralph_state.py  # State management
backend/api/ralph_api.py    # API endpoints
```

**Pipeline:**
1. Context Intake → 2. Execution Loop → 3. Architect Verification → 4. Cleanup → 5. Completion

**Trigger keywords:** `ralph`, "don't stop", "keep going", "must complete", "finish this"

### $team Skill
**Files creati/aggiornati:**
```
skills/team/SKILL.md                    # Metadata
skills/team/TEAM.md                    # Execution protocol
backend/orchestration/coordinator.py   # Extended with team methods
backend/api/coordinator_api.py          # New team endpoints
```

**Pipeline:**
`team-plan → team-prd → team-exec → team-verify → team-fix`

**Team endpoints:**
- `POST /{id}/team/start` - Avvia team con N worker
- `GET /{id}/team/status` - Stato esecuzione
- `POST /{id}/team/shutdown` - Chiude team

### Keyword Detection System
**Files creati:**
```
backend/core/keyword_detection.py  # Detection engine
backend/api/keywords_api.py       # API endpoints
frontend/src/api/keywordsApi.ts  # TypeScript client
frontend/src/components/chat/KeywordBadge.tsx  # UI badge
```

**Keywords supportate:**
| Keyword | Action |
|---------|--------|
| ralph, "don't stop", "keep going" | $ralph |
| team, swarm, "parallel agents" | $team |
| analyze, investigate | analyze |
| plan this, "let's plan" | plan |
| ultrawork, ulw, parallel | ultrawork |
| ultraqa, qa | ultraqa |
| tdd, "test first" | tdd |
| code review | code-review |
| security review | security-review |
| cancel, stop, abort | cancel |
| "fix build", "type errors" | build-fix |
| web-clone, "clone site" | web-clone |

**API endpoints:**
- `GET /api/keywords/mappings` - Lista tutti i mappings
- `POST /api/keywords/detect` - Rileva keywords nel testo

### Mode Management System
**Files creati:**
```
backend/core/modes.py   # ModeManager
backend/api/modes_api.py  # API endpoints
```

**Features:**
- Track active modes (ralph, team, analyze, plan, etc.)
- Mode transitions
- Context preservation per mode
- Integration with keyword detection

**API endpoints:**
- `GET /api/modes/active` - Get active modes
- `POST /api/modes/enter` - Enter a mode
- `POST /api/modes/exit` - Exit a mode
- `POST /api/modes/clear` - Clear all modes

### $analyze Skill
**Files creati:**
```
skills/analyze/SKILL.md  # Metadata
```
**Features:** Evidence-driven investigation, systematic analysis

### $plan Skill
**Files creati:**
```
skills/plan/SKILL.md  # Metadata
```
**Features:** Strategic planning, task breakdown, milestone setting

### $tdd Skill
**Files creati:**
```
skills/tdd/SKILL.md  # Metadata
```
**Features:** Test-driven development workflow, red-green-refactor

### $code-review Skill
**Files creati:**
```
skills/code-review/SKILL.md  # Metadata
```
**Features:** Systematic code review, best practices checklist

### $cancel Skill
**Files creati:**
```
skills/cancel/SKILL.md  # Metadata
```
**Features:** Workflow cancellation, cleanup, state reset

### $ultraqa Skill
**Files creati:**
```
skills/ultraqa/SKILL.md  # Metadata
```
**Features:** QA cycling, test-run-fix loop, quality assurance

### $security-review Skill
**Files creati:**
```
skills/security-review/SKILL.md  # Metadata
```
**Features:** Security audit, vulnerability assessment, OWASP checklist

---

## oh-my-openagent Porting

### Feature portate da oh-my-openagent

| Feature | Status |
|---------|--------|
| **Agent System** | ✅ Completato |
| **Hook System** | ✅ Completato |
| **Hashline Edit Tool** | ✅ Completato |
| **Commands System** | ✅ Completato |

### Agent System (9 agents ported)

| Agent | Description | Status |
|-------|-------------|--------|
| **Sisyphus** | Main orchestrator, plans and delegates | ✅ |
| **Prometheus** | Strategic planner with interview mode | ✅ |
| **Hephaestus** | Autonomous deep worker | ✅ |
| **Oracle** | Architecture, review, debugging | ✅ |
| **Explore** | Fast codebase grep | ✅ |
| **Librarian** | Documentation and multi-repo analysis | ✅ |
| **Atlas** | Todo-list orchestrator | ✅ |
| **Metis** | Plan consultant, pre-planning | ✅ |
| **Momus** | Plan reviewer | ✅ |

### Hook System (5 hooks ported)

| Hook | Description | Status |
|------|-------------|--------|
| **KeywordDetectorHook** | Detects keywords in messages | ✅ |
| **RalphLoopHook** | Self-referential loop continuation | ✅ |
| **ContextInjectorHook** | AGENTS.md/README injection | ✅ |
| **SessionRecoveryHook** | Error recovery | ✅ |
| **CommentCheckerHook** | AI slop comment detection | ✅ |

### Tools

| Tool | Description | Status |
|------|-------------|--------|
| **HashlineEditTool** | Hash-anchored safe editing | ✅ |

### Commands

| Command | Description | Status |
|---------|-------------|--------|
| **init-deep** | Generate hierarchical AGENTS.md | ✅ |
| **ralph-loop** | Self-referential loop | ✅ |
| **start-work** | Execute from Prometheus plan | ✅ |
| **handoff** | Create context summary | ✅ |

### Remaining oh-my-openagent features to port

| Feature | Status |
|---------|--------|
| MCP integration | ✅ Completato |
| LSP tools | ✅ Completato |
| AST-grep tools | ✅ Completato |
| Skill-embedded MCPs | ✅ Completato |
| Config system | ✅ Completato |

### oh-my-openagent Files Created

```
backend/orchestration/agents/
├── __init__.py
├── base.py              # Base agent class
├── sisyphus.py          # Main orchestrator
├── prometheus.py         # Strategic planner
├── hephaestus.py         # Deep worker
├── oracle.py             # Review agent
├── explore.py            # Fast grep
├── librarian.py          # Documentation
├── atlas.py              # Todo orchestrator
├── metis.py              # Plan consultant
└── momus.py             # Plan reviewer

backend/hooks/
├── __init__.py
├── events.py
├── registry.py
└── handlers/
    ├── __init__.py
    └── keyword_detector.py

backend/tools/
├── __init__.py
└── hashline_edit.py

backend/commands/
├── __init__.py
├── registry.py
└── core.py

backend/tests/
├── test_agents.py
├── test_hooks.py
└── test_hashline.py

docs/oh-my-openagent-porting.md
```

### Config System (NEW)

```
backend/tenderclaw_config/
├── __init__.py            # Main exports
├── jsonc.py               # JSONC parser (supports // and /* */ comments)
├── manager.py             # ConfigManager with hierarchical loading
└── schemas/
    ├── __init__.py        # Schema exports
    ├── agent_overrides.py  # AgentOverrideConfig (21 fields)
    ├── background_task.py  # BackgroundTaskConfig, CircuitBreakerConfig
    ├── categories.py       # CategoryConfig, 8 built-in categories
    ├── comment_checker.py  # CommentCheckerConfig
    ├── experimental.py     # ExperimentalConfig, DynamicContextPruning
    ├── git_master.py       # GitMasterConfig
    ├── hooks.py            # HookConfig, HooksConfig (48 hooks)
    ├── ralph_loop.py       # RalphLoopConfig
    ├── sisyphus.py         # SisyphusConfig
    ├── skills.py           # SkillsConfig, SkillDefinition
    └── tenderclaw_config.py # Root TenderClawConfig

frontend/src/types/
└── config.ts             # TypeScript types mirroring Python schemas
```

**Config System Features:**
- JSONC parser (comments in JSON files)
- Hierarchical config loading (defaults < file < env < runtime)
- Pydantic validation with sensible defaults
- 45 pytest tests

## Cronologia Modifiche

| Data | Fase | Descrizione |
|------|------|-------------|
| 2026-04-05 | - | Piano creato |
| 2026-04-05 | Fase 1 | Completata: Migrations + Usage Tracker + Cost UI |
| 2026-04-05 | Fase 2 | Completata: Keybindings System + Integration |
| 2026-04-05 | Fase 3 | Completata: History API paginata + Detail screen |
| 2026-04-05 | Fase 4 | Completata: Vim Mode + Buddy Companion + Coordinator |
| 2026-04-05 | Fase 5 | Completata: Remote Bridge + Voice Mode + Analytics |
| 2026-04-06 | oh-my-codex | Completato: ralph, team, keyword detection |
| 2026-04-06 | oh-my-codex | Completato: analyze, plan, tdd, code-review, cancel, ultraqa, security-review |
| 2026-04-06 | oh-my-codex | Completato: autopilot, deep-interview, doctor, git-master |
| 2026-04-06 | oh-my-codex | Completato: visual-verdict, web-clone, ecomode, deepsearch, swarm, ultrawork, worker, trace |
| 2026-04-06 | oh-my-openagent | Agent system completato (9 agents) |
| 2026-04-06 | oh-my-openagent | Hook system completato (5 hooks) |
| 2026-04-06 | oh-my-openagent | Hashline edit tool completato |
| 2026-04-06 | oh-my-openagent | Commands system completato (4 commands) |
| 2026-04-06 | oh-my-openagent | Config system completato (15 schemas, 45 tests) |
| 2026-04-06 | openclaw | Advanced Model Fallback System (auth profiles, 2-lane cooldown, 32 tests) |

### OpenClaw Advanced Fallback System

```
backend/services/advanced_fallback/
├── __init__.py              # Main exports
├── errors.py                # FailoverError classification (10 reasons)
├── auth_profiles.py         # Multi-key management with rotation
├── cooldown.py              # Two-lane cooldown (transient + persistent)
├── fallback.py              # runWithModelFallback orchestration
└── policy.py                # Fallback decision policy

tenderclaw_config/schemas/experimental.py
└── AdvancedFallbackConfig   # Opt-in via experimental.advanced_fallback
```

**Features (Opt-in via config):**
- Auth profiles: Multi-API-key management with round-robin rotation
- Two-lane cooldown: Transient (30s-5min) vs Persistent (exponential to days)
- Model fallback: Automatic switch to fallback models on failure
- Probe system: Recovery testing with throttling
- 32 pytest tests

**Config Example:**
```yaml
experimental:
  advancedFallback:
    enabled: true
    fallbackModels:
      - "openai/gpt-5"
      - "google/gemini-2.5"
    useAuthProfiles: true
    maxRetriesPerModel: 2
```
