---
name: ralplan
description: Consensus planning via Planner + Architect + Critic triad before execution
trigger: ralplan
argument-hint: "[--rounds <N>] <task or feature description>"
system: false
---

# /ralplan — Consensus Planning

## Trigger

`/ralplan <task>` or "ralplan", "consensus plan", "planner architect critic", "planning triad"

## Description

Ralplan runs a **three-role planning triad** — Planner, Architect, and Critic — that must reach consensus before any code is written. It prevents premature execution by requiring all three roles to converge on a single implementation plan.

## When to Use

- Feature is large enough to benefit from multi-perspective planning
- Previous attempts at the task produced conflicting approaches
- Stakeholder (user) wants auditability before execution starts
- Coming from `deep-interview` or `deepsearch` with a crystallized spec

## Do Not Use When

- Task is a trivial one-liner fix
- User explicitly says "just do it" or invokes `/autopilot` directly
- A consensus plan already exists in `.omx/plans/`

## Roles

| Role | Responsibility |
|------|----------------|
| **Planner** | Proposes the implementation approach: files, steps, interfaces |
| **Architect** | Evaluates structural fit, technical debt, scalability, coupling |
| **Critic** | Stress-tests assumptions, identifies risks, edge cases, missing tests |

## Flow

### Phase 0: Context Intake
1. Load any existing spec from `.omx/specs/` or `.tenderclaw/state/plans/`
2. Summarize the task in ≤ 3 sentences

### Phase 1: Planner Turn
1. Produce a concrete implementation plan:
   - Files to create or modify (exact paths)
   - Key functions / classes to add
   - Step order with rationale
2. Estimate complexity: Low / Medium / High
3. Flag any external dependencies

### Phase 2: Architect Turn
1. Review the Planner's proposal
2. Evaluate: does it fit the existing architecture?
3. Propose structural improvements or alternatives
4. Rate feasibility: 1–5

### Phase 3: Critic Turn
1. Review both Planner and Architect outputs
2. Identify: missing tests, security gaps, performance risks, rollback difficulty
3. Assign risk level: Low / Medium / High / Critical
4. Propose mitigations for each risk

### Phase 4: Consensus Round
Repeat (up to `--rounds` times, default 2) until consensus:
- Each role re-evaluates after seeing the others' input
- Consensus = all three rates feasibility >= 3 AND risk <= Medium
- If no consensus after max rounds: output divergence report and halt

### Phase 5: Crystallize Plan
Write final consensus plan to `.omx/plans/ralplan-{slug}-{timestamp}.md`:
```
# Consensus Plan: {task}
## Approach (Planner)
## Architecture Notes (Architect)
## Risk Register (Critic)
## Final Steps (ordered)
## Acceptance Criteria
```

## Execution Bridge

After crystallization, offer:
1. **$autopilot** — Execute the consensus plan (recommended)
2. **$ralph** — Persistent execution with re-verification
3. **$team** — Parallel worker execution
4. **Refine further** — Another consensus round

## Rules

- Never emit code during planning phases
- Planner proposes, Architect validates, Critic challenges — roles do not swap
- If Critic rates risk Critical, HALT and request user guidance
- Consensus plan is the single source of truth for execution

## Agents

- metis
- sisyphus
- sentinel

## Keywords

- ralplan, consensus plan, planner architect critic, planning triad, three-role planning
