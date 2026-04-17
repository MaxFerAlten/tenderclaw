---
name: writing-plans
description: Bite-sized implementation plans with exact paths, complete code, zero placeholders
trigger: writing-plan
system: true
---

# Writing Plans — Precise Implementation Planning

## Purpose

Transform a design or requirement into a sequence of **small, atomic implementation tasks**.
Each task must be completable in 2-5 minutes and produce a verifiable result.

## Flow

1. **Analyze Scope**: Read the design doc or requirement. Identify all files to create/modify.
2. **Dependency Order**: Sort tasks by dependency — what must exist before what.
3. **Decompose**: Break each file change into the smallest possible atomic step.
4. **Specify Completely**: For each task, provide:
   - Exact file path
   - What to add/change/remove
   - Complete code (no placeholders, no TODOs, no stubs)
   - Expected command to verify (test, lint, type-check)
5. **Review Plan**: Verify no task depends on a later task. Verify no gaps.

## Task Format

Each task in the plan MUST follow this structure:

```
### Task N: [Short description]
- **File**: `exact/path/to/file.py`
- **Action**: CREATE | MODIFY | DELETE
- **Code**: (complete implementation, not a sketch)
- **Verify**: `pytest tests/test_xxx.py -k test_name` or equivalent
- **Depends on**: Task M (if any)
```

## Rules

- Every task must have an explicit file path. No "somewhere in the codebase".
- Every task must have complete code. No `# TODO`, no `pass`, no `...`, no `NotImplementedError`.
- Every task must have a verification command that proves it works.
- Tasks should be ordered so that each can be executed independently after its dependencies.
- Maximum 5 minutes per task. If a task is bigger, split it.
- The plan must cover tests. Test tasks come BEFORE or WITH implementation tasks (TDD style preferred).

## Anti-Patterns

- Tasks without file paths
- Placeholder code (`# implement this`, `pass`, `...`)
- Tasks too large to verify in one step
- Missing verification commands
- Circular dependencies between tasks
- Plans that assume "the reader will figure out the details"

## Output

Plans are saved to `.tenderclaw/plans/` as structured markdown.
Each plan gets a unique ID: `PLAN-{timestamp}-{short-slug}`.

## Agents

- sisyphus (main orchestrator for execution)
- oracle (architecture review of the plan)

Task: {{ARGUMENTS}}
