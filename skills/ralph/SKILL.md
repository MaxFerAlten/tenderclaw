---
name: ralph
description: Autonomous execution loop that never stops until task completion with architect verification
trigger: ralph
---

# Ralph - Autonomous Execution Loop

Ralph is a persistence loop that keeps working on a task until it is fully complete and architect-verified.

## When to Use
- User says "ralph", "don't stop", "keep going", "must complete"
- Task requires guaranteed completion with verification
- Work may span multiple iterations

## Pipeline

### Phase 1: Context Intake
1. Create context snapshot at `.tenderclaw/state/ralph/{task-slug}-{timestamp}.md`
2. Include: task statement, desired outcome, known facts, constraints

### Phase 2: Execution Loop
1. **Delegate in parallel** to specialist agents
2. **Run long operations in background** (builds, tests)
3. **Verify completion** with fresh evidence:
   - Run tests and read output
   - Run build and confirm success
   - Check for 0 errors

### Phase 3: Architect Verification
- STANDARD tier: <5 files, <100 lines
- THOROUGH tier: >20 files or security changes

### Phase 4: Cleanup Pass
- Run code cleanup on changed files
- Re-verify tests still pass

### Phase 5: Completion
- Cancel mode and cleanup state files

## State Files
- `.tenderclaw/state/ralph/{task-slug}.md` - Current state
- `.tenderclaw/state/ralph/progress.json` - Progress tracking

## Verification Checklist
- [ ] All requirements met (no scope reduction)
- [ ] Zero pending TODO items
- [ ] Fresh test run: all pass
- [ ] Fresh build: success
- [ ] Architect verification: APPROVED
- [ ] Cleanup pass completed
- [ ] Post-cleanup regression: pass