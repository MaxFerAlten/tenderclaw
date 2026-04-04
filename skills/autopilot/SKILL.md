# /autopilot — Autonomous End-to-End Pipeline

## Trigger
`/autopilot <task>`

## Flow
1. **Intent Classification**: Determine task type (implement, fix, refactor).
2. **Planning**: Metis creates plan, Oracle researches unknowns.
3. **Execution**: Sisyphus/Hephaestus implement the plan.
4. **Verification**: Momus reviews, Sentinel checks security.
5. **Fix Loop**: Up to 3 iterations if verification fails.
6. **Completion**: Report results with summary.

## Rules
- Fully autonomous — no user intervention during execution.
- Each stage must succeed before proceeding.
- If fix loop exceeds 3 attempts, report failure and ask user.
- Accumulate wisdom from the completed task.
