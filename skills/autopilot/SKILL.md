---
name: autopilot
description: Full autonomous execution from idea to working code
---

# /autopilot — Autonomous End-to-End Pipeline

## Trigger

`/autopilot <task>` or "autopilot", "autonomous", "build me", "make me"

## Purpose

Autopilot takes a brief product idea and autonomously handles the full lifecycle: requirements analysis, technical design, planning, parallel implementation, QA cycling, and multi-perspective validation.

## When to Use

- User wants end-to-end autonomous execution from an idea to working code
- Task requires multiple phases: planning, coding, testing, and validation
- User wants hands-off execution and is willing to let the system run to completion

## Do Not Use When

- User wants to explore options or brainstorm — use `$plan`
- Task is a quick fix or small bug — use direct executor or `$ralph`
- User wants to review or critique an existing plan — use `$plan --review`

## Flow

### Phase 0: Context Intake
- Derive task slug from request
- Load existing context snapshot if available
- Create context snapshot with: task statement, desired outcome, constraints, unknowns
- Run explore for brownfield facts if ambiguous

### Phase 1: Expansion
- Analyst: Extract requirements
- Architect: Create technical specification
- Output: `.omx/plans/autopilot-spec.md`

### Phase 2: Planning
- Architect: Create implementation plan
- Critic: Validate plan
- Output: `.omx/plans/autopilot-impl.md`

### Phase 3: Execution
- Implement plan using `$ralph` + parallel work
- LOW-tier: Simple tasks
- STANDARD-tier: Standard tasks
- THOROUGH-tier: Complex tasks
- Run independent tasks in parallel

### Phase 4: QA
- Build, lint, test, fix failures
- Cycle up to 5 times
- Stop if same error repeats 3x (fundamental issue)

### Phase 5: Validation
- Architect: Functional completeness
- Security-reviewer: Vulnerability check
- Code-reviewer: Quality review
- All must approve; fix and re-validate on rejection

### Phase 6: Cleanup
- Clear all mode state
- Report completion with summary

## State Management

```
State: autopilot
  - active: boolean
  - current_phase: expansion|planning|execution|qa|validation|complete
  - context_snapshot_path: string
  - started_at: timestamp
  - completed_at: timestamp
```

## Keywords

- autopilot, auto pilot, autonomous
- build me, create me, make me
- full auto, handle it all
- I want a/an...

## Recommended Pipeline

```
deep-interview -> ralplan -> autopilot
```

For ambiguous requests, prefer the clarity pipeline first.

## Escalation

- Stop when same QA error persists 3 cycles
- Stop when validation fails after 3 re-validation rounds
- Stop on "stop", "cancel", "abort"
- Redirect to deep-interview if requirements too vague

## Final Checklist

- [ ] All 6 phases completed
- [ ] All validators approved in Phase 5
- [ ] Tests pass
- [ ] Build succeeds
- [ ] State files cleaned up
- [ ] User informed of completion with summary
