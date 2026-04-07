---
name: ultraqa
description: QA cycling workflow - test, verify, fix, repeat until goal met
---

# UltraQA — Autonomous QA Cycling

## Purpose

UltraQA is an autonomous QA cycling workflow that runs until your quality goal is met.

**Cycle**: qa-tester → architect verification → fix → repeat

## When to Use

- User wants tests to pass before proceeding
- QA verification needed before merging
- Quality gate enforcement
- User says "ultraqa", "run tests until pass", "qa cycle"

## Goal Types

| Invocation | Goal Type | What to Check |
|------------|-----------|---------------|
| `ultraqa --tests` | tests | All test suites pass |
| `ultraqa --build` | build | Build succeeds with exit 0 |
| `ultraqa --lint` | lint | No lint errors |
| `ultraqa --typecheck` | typecheck | No TypeScript errors |
| `ultraqa --custom "pattern"` | custom | Custom success pattern |

## Cycle Workflow

### Cycle N (Max 5)

1. **RUN QA**: Execute verification based on goal type
   - `--tests`: Run project's test command
   - `--build`: Run project's build command
   - `--lint`: Run project's lint command
   - `--typecheck`: Run project's type check command
   - `--custom`: Run appropriate command and check for pattern

2. **CHECK RESULT**: Did the goal pass?
   - **YES** → Exit with success
   - **NO** → Continue to step 3

3. **ARCHITECT DIAGNOSIS**: Analyze failure
   - Provide root cause analysis
   - List specific fix recommendations

4. **FIX ISSUES**: Apply recommendations

5. **REPEAT**: Go back to step 1

## Exit Conditions

| Condition | Action |
|-----------|--------|
| **Goal Met** | "ULTRAQA COMPLETE: Goal met after N cycles" |
| **Cycle 5 Reached** | "ULTRAQA STOPPED: Max cycles. Diagnosis: ..." |
| **Same Failure 3x** | "ULTRAQA STOPPED: Same failure detected 3x. Root cause: ..." |
| **Environment Error** | "ULTRAQA ERROR: [dependency/command issue]" |

## Observability

Output progress each cycle:
```
[ULTRAQA Cycle 1/5] Running tests...
[ULTRAQA Cycle 1/5] FAILED - 3 tests failing
[ULTRAQA Cycle 1/5] Diagnosing...
[ULTRAQA Cycle 1/5] Fixing: auth.test.ts - missing mock
[ULTRAQA Cycle 2/5] Running tests...
[ULTRAQA Cycle 2/5] PASSED - All 47 tests pass
[ULTRAQA COMPLETE] Goal met after 2 cycles
```

## State Management

```
State: ultraqa
  - active: boolean
  - current_phase: qa|diagnose|fix|complete
  - iteration: number
  - goal_type: tests|build|lint|typecheck|custom
  - started_at: timestamp
  - completed_at: timestamp
```

## Keywords

- ultraqa, qa cycle, run tests until pass
- quality gate, test until green

## Combine with Other Skills

**With $ralph:**
```
$ralph implement and run ultraqa
```

**With $team:**
```
$team implement and run ultraqa for all modules
```

**With $autopilot:**
```
$autopilot build feature with ultraqa quality gates
```

## Important Rules

1. **PARALLEL when possible** - Run diagnosis while preparing fixes
2. **TRACK failures** - Record each failure to detect patterns
3. **EARLY EXIT on pattern** - 3x same failure = stop and surface
4. **CLEAR OUTPUT** - User should always know current cycle
5. **CLEAN UP** - Clear state file on completion or cancellation
