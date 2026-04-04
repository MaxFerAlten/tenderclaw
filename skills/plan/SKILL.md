# /plan — Structured Planning Skill

## Trigger
`/plan <description>`

## Agents
- **metis** (primary): Creates detailed implementation plan
- **oracle** (support): Research unknowns

## Flow
1. Clarify the goal with the user (1-2 questions max).
2. Research existing code structure relevant to the task.
3. Produce a step-by-step plan with file paths, changes, and dependencies.
4. Highlight risks and open questions.

## Output Format
```
## Plan: <title>

### Steps
1. [file_path] — description of change
2. [file_path] — description of change

### Risks
- Risk description → mitigation

### Open Questions
- Question for the user
```
