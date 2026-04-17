# Blueprint Audit — TenderClaw-50

**Date**: 2026-04-11  
**Auditor**: Sprint 6 Hardening pass  
**Scope**: Divergences between the TenderClaw blueprint documentation (`docs/tenderclaw.md`, `docs/oh-my-openagent-porting.md`) and the actual Python implementation after Sprints 0–6.

---

## 1. Implemented — Present in Blueprint and Code

| Feature | Blueprint reference | Implementation |
|---------|-------------------|----------------|
| Skill discovery (SKILL.md) | `oh-my-openagent-porting.md` §Skills | `backend/core/skills.py` — `SkillRegistry`, `discover_skills()` |
| Intent Gate | `tenderclaw.md` §Pipeline | `backend/orchestration/intent_gate.py` — `classify_intent()`, `IntentGateResult` |
| Hook lifecycle | `tenderclaw.md` §Hooks | `backend/hooks/engine.py` — `HookRegistry`, `HookEntry` |
| Keyword detection | `oh-my-openagent-porting.md` §Keyword triggers | `backend/core/keyword_detection.py` — `KeywordDetector` (24 mappings) |
| Memory (multi-scope) | `tenderclaw.md` §Memory | `backend/memory/` — user/repo/team/session scopes |
| Role routing | Sprint 4 spec | `backend/services/role_router.py` — `RoleRouter`, tier+posture |
| Worker pool | Sprint 4 spec | `backend/workers/pool.py` — backpressure, health checks |
| Plan store | Sprint 4 spec | `backend/orchestration/plan_store.py` — canonical ID, reserve before bootstrap |
| Skill auto-select | Sprint 5 spec | `backend/core/skills.py` — `SkillSelector`, `SkillMatch`, trace |
| ralplan skill | Sprint 5 spec | `skills/ralplan/SKILL.md` — Planner+Architect+Critic triad |
| REST gateway | Sprint 3 spec | `backend/api/gateway.py` — `GatewayRequest/Response` contract |
| WS sequence numbers | Sprint 3 spec | `backend/api/ws.py` — `WSSeqMixin`, per-session counter |
| i18n (it/en) | Sprint 6 spec | `backend/i18n/` — `I18nManager`, `en.json`, `it.json` |

---

## 2. Divergences — Blueprint vs Implementation

### 2.1 Intent Gate: no async cache in blueprint
- **Blueprint**: Intent gate is a stateless classifier call.
- **Implementation** (Sprint 6): `IntentCache` adds a 3-turn sliding-window cache per session (`_session_caches` dict).  
- **Impact**: More stable intent routing but introduces module-level mutable state. Cache must be cleared on session reset via `clear_intent_cache(session_id)`.

### 2.2 Keyword detection: two surfaces, now deduplicated
- **Blueprint**: Single keyword detection engine referenced.
- **Before Sprint 6**: Two independent engines existed — `backend/core/keyword_detection.py` (24 mappings) and `backend/hooks/handlers/keyword_detector.py` (7 modes, different keyword lists).
- **After Sprint 6**: `KeywordDetectorHook` now delegates to `keyword_detector` singleton. Single source of truth. Any new keyword mapping added to `keyword_detection.py` is automatically visible to the hook.

### 2.3 Hook MODIFY strategy not in original blueprint
- **Blueprint**: Hook results described as "merge data into event".
- **Implementation** (Sprint 6): Explicit `ConflictResolution` enum (`LAST_WIN | FIRST_WIN | MERGE`) per hook registration. Default is `LAST_WIN` (backwards-compatible).
- **Impact**: No breaking change — existing hooks default to LAST_WIN. New hooks can opt into FIRST_WIN or MERGE as needed.

### 2.4 AST-grep / LSP routing
- **Blueprint** (`TenderClaw-50-chatgpt.md` Sprint 6): Mentions routing between grep / AST-grep / LSP.
- **Implementation**: No AST-grep or LSP integration has been built yet. `Grep` tool and `KeywordDetector.detect()` cover most search cases.  
- **Status**: **Not yet implemented**. Tracked as future work.

### 2.5 `docs/blueprint-audit.md` not in original blueprint
- **Blueprint**: Does not mention an audit document.
- **Implementation**: This file — created per Sprint 6 spec (Gemini/Sonnet variants).

### 2.6 Superpowers loader: `system: true` frontmatter
- **Blueprint**: Mentions `system: true` flag for always-active skills.
- **Implementation** (`backend/plugins/superpowers_loader.py`): Flag parsed but not enforced in the pipeline — skills marked `system: true` are loaded but not injected automatically.  
- **Status**: Partially implemented.

### 2.7 PermissionDialog "Always allow" checkbox
- **Blueprint** (Sprint 3): UI checkbox to persist tool permission.
- **Implementation**: Checkbox is rendered in `frontend/src/components/tools/PermissionDialog.tsx` but persistence (writing to `~/.tenderclaw/permissions.json`) is not yet wired up.  
- **Status**: Partially implemented (UI only).

---

## 3. Not Yet Implemented

| Feature | Blueprint reference | Priority |
|---------|-------------------|----------|
| AST-grep routing | Sprint 6 hardening | Low |
| LSP integration | Sprint 6 hardening | Low |
| `system: true` auto-injection | Sprint 0 design | Medium |
| Permission persistence (Always allow) | Sprint 3 UI | Medium |
| Relay transport | `gateway.py` §Relay | Low |
| Deep-interview skill | Sprint 5 discovery | Medium |
| Visual-verdict skill | `keyword_detection.py` | Low |

---

## 4. Test Coverage Status (after Sprint 6)

| Module | Test file | Tests |
|--------|-----------|-------|
| `core/skills.py` | `test_skill_selection.py`, `test_skill_routing.py`, `test_skill_prompt_injection.py` | 80 |
| `orchestration/intent_gate.py` | `test_sprint6_hardening.py` | — |
| `hooks/engine.py` | `test_sprint6_hardening.py` | — |
| `core/keyword_detection.py` | `test_sprint6_hardening.py` | — |
| `i18n/i18n_manager.py` | `test_sprint6_hardening.py` | — |
| `orchestration/plan_store.py` | `test_sprint4_omx_runtime.py` | 65 |
| `workers/pool.py` | `test_sprint4_omx_runtime.py` | — |
| `memory/` | `test_memory_manager.py` et al. | 56 |

---

## 5. Recommendations

1. **Wire `system: true` injection** — implement in `superpowers_loader.py` → `build_system_prompt()` to automatically prepend always-active skills.
2. **Persist "Always allow"** — write approved tool patterns to `~/.tenderclaw/permissions.json` and load on session start.
3. **Session cache cleanup** — call `clear_intent_cache(session_id)` in `SESSION_END` hook to prevent unbounded growth of `_session_caches`.
4. **AST-grep stub** — at minimum add a `KeywordMapping` for `ast-grep` → route to `Grep` with `--pcre2` for now.
