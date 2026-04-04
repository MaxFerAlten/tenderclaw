# /team — Parallel Team Execution Skill

## Trigger
`/team <task>`

## Pipeline
`plan → exec → verify → fix (max 3) → complete`

## Phase Agents
| Phase | Agent | Role |
|-------|-------|------|
| plan | metis, oracle | Strategy + research |
| exec | sisyphus, hephaestus | Implementation |
| verify | momus, sentinel | Review + security |
| fix | fixer | Bug fixes from review |

## Rules
- Each phase must complete before the next starts.
- Verify phase can trigger up to 3 fix cycles.
- All agents share context via message history.
- Pipeline reports progress via WebSocket agent_switch events.
