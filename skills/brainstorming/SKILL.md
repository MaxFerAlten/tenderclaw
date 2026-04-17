---
name: brainstorming
description: Design-first workflow with HARD-GATE — no code until design is approved
trigger: brainstorm
system: true
---

# Brainstorming — Design-First HARD-GATE

## HARD-GATE RULE

**NO CODE MAY BE WRITTEN until ALL of the following gates are passed.**
This is non-negotiable. Any attempt to write, edit, or generate implementation
code before gate approval MUST be rejected.

## Flow

1. **Explore**: Understand the problem space. Read existing code, docs, tests. Identify constraints, dependencies, and affected surfaces.
2. **Clarify**: Ask the user focused questions to resolve ambiguities. Do NOT assume. Each question must reduce ambiguity measurably.
3. **Propose 3 Approaches**: Generate at least 3 distinct solution approaches with trade-offs (complexity, risk, performance, maintainability).
4. **Design Document**: Produce a structured design doc with:
   - Objectives (what success looks like)
   - Constraints (what must NOT change)
   - UX/API surface (how it looks to consumers)
   - Risks (what could go wrong)
   - Expected outputs (files to create/modify, tests to write)
5. **Self-Review**: Critique your own design. Identify weak points, missing edge cases, over-engineering.
6. **User Approval**: Present the design and WAIT for explicit user approval before ANY implementation.

## Gates

- [ ] Problem space explored (existing code read)
- [ ] Ambiguities resolved (questions asked and answered)
- [ ] 3+ approaches proposed with trade-offs
- [ ] Design document complete (objectives, constraints, risks, outputs)
- [ ] Self-review performed
- [ ] User has explicitly approved the design

## Rules

- NEVER skip straight to code. The purpose of this skill is to THINK FIRST.
- If the user says "just do it" or "skip design", remind them of the HARD-GATE and ask which gates they want to mark as passed.
- All design artifacts are saved to `.tenderclaw/designs/`.
- The design document must list EVERY file that will be created or modified.
- No placeholder code. No TODO comments. No "implement later" stubs.

## Anti-Patterns

- Writing code before the design is approved
- Skipping the self-review step
- Proposing only one approach
- Leaving ambiguities unresolved
- Design docs without concrete file paths

## Agents

- oracle (research & architecture analysis)
- metis (strategy & gap analysis)
- prometheus (requirements gathering)

Task: {{ARGUMENTS}}
