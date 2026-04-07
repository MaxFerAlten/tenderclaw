---
name: cancel
description: Cancel any active workflow mode
trigger: cancel
---

# Cancel Skill

Cancel any active TenderClaw mode (ralph, team, analyze, plan, tdd).

## Modes to Cancel
- **ralph**: Stop autonomous execution loop
- **team**: Shutdown team workers
- **analyze**: End analysis session
- **plan**: Cancel planning
- **tdd**: Stop TDD session

## Execution
1. Detect active mode
2. Clear mode state
3. Clean up resources
4. Report cancellation

## Cleanup
- Clear mode state in `.tenderclaw/state/`
- Shutdown team workers if team mode
- Preserve progress where possible

Task: {{ARGUMENTS}}
