---
name: deep-interview
description: Socratic deep interview with mathematical ambiguity gating before execution
argument-hint: "[--quick|--standard|--deep] [--autoresearch] <idea or vague description>"
---

# /deep-interview — Socratic Requirements Gathering

## Trigger

`/deep-interview <topic>` or "deep interview", "interview me", "ask me everything"

## Purpose

Deep Interview is an intent-first Socratic clarification loop before planning or implementation. It turns vague ideas into execution-ready specifications.

## When to Use

- Request is broad, ambiguous, or missing concrete acceptance criteria
- You need a requirements artifact before handing off to planning/execution
- User wants to avoid misaligned implementation from underspecified requirements

## Do Not Use When

- Request already has concrete file/symbol targets and clear acceptance criteria
- User explicitly asks to skip planning and execute immediately
- A complete PRD/plan already exists

## Depth Profiles

| Profile | Threshold | Max Rounds | Use Case |
|---------|-----------|-----------|----------|
| `--quick` | <= 0.30 | 5 | Fast pre-PRD pass |
| `--standard` | <= 0.20 | 12 | Full requirement interview (default) |
| `--deep` | <= 0.15 | 20 | High-rigor exploration |

## Execution Policy

- Ask ONE question per round
- Ask about intent and boundaries before implementation detail
- Target weakest clarity dimension each round
- Stay on same thread until one layer deeper
- Complete at least one explicit assumption pressure pass
- Reduce user effort: ask only highest-leverage unresolved question

## Clarity Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Intent Clarity | 30% | Why user wants this |
| Outcome Clarity | 25% | What end state they want |
| Scope Clarity | 20% | How far change should go |
| Constraint Clarity | 15% | Technical/business limits |
| Success Criteria | 10% | How completion is judged |
| Context Clarity | 10% | Brownfield understanding (if applicable) |

## Ambiguity Score Formula

```
Greenfield: ambiguity = 1 - (intent × 0.30 + outcome × 0.25 + scope × 0.20 + constraints × 0.15 + success × 0.10)

Brownfield: ambiguity = 1 - (intent × 0.25 + outcome × 0.20 + scope × 0.20 + constraints × 0.15 + success × 0.10 + context × 0.10)
```

## Flow

### Phase 0: Preflight Context Intake
1. Derive task slug from arguments
2. Load existing context snapshot if available
3. Create context snapshot with: task statement, desired outcome, constraints, unknowns

### Phase 1: Initialize
1. Parse depth profile
2. Detect brownfield vs greenfield
3. Initialize state
4. Announce kickoff with profile, threshold, ambiguity

### Phase 2: Socratic Interview Loop
Repeat until ambiguity <= threshold or max rounds reached.

Each Round:
1. Generate question targeting weakest dimension
2. Ask one question
3. Score ambiguity
4. Report progress
5. Persist state

### Challenge Modes
- **Contrarian** (round 2+): Challenge core assumptions
- **Simplifier** (round 4+): Probe minimal viable scope
- **Ontologist** (round 5+): Ask for essence-level reframing

### Phase 3: Crystallize Artifacts
- Write transcript to `.omx/interviews/{slug}-{timestamp}.md`
- Write spec to `.omx/specs/deep-interview-{slug}.md`

## Execution Bridge

After crystallization, offer handoff options:

1. **$ralplan** — Consensus planning (recommended)
2. **$autopilot** — Full execution
3. **$ralph** — Persistent execution
4. **$team** — Coordinated parallel execution
5. **Refine further** — Continue interviewing

## Escalation

- Stop on "stop/cancel/abort"
- Force Ontologist if ambiguity stalls 3 rounds
- Hard cap at max rounds with warning
- Allow early exit if all dimensions >= 0.9

## Keywords

- deep interview, interview me, ask me everything
- don't assume, ouroboros

## Recommended Pipeline

```
deep-interview -> ralplan -> autopilot
```

- Stage 1 (deep-interview): Clarity gate
- Stage 2 (ralplan): Feasibility + architecture gate
- Stage 3 (autopilot): Execution + QA + validation gate
