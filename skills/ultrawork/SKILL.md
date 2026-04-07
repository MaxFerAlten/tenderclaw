---
name: ultrawork
description: Parallel execution engine for high-throughput task completion
---

# Ultrawork Skill

Parallel execution engine that runs multiple agents simultaneously for independent tasks.

## When to Use

This skill activates when:
- Multiple independent tasks can run simultaneously
- User says "ulw", "ultrawork", "parallel"
- You need to delegate work to multiple agents at once
- Task benefits from concurrent execution

## Do Not Use When

- Task requires guaranteed completion with verification — use `$ralph`
- Task requires full autonomous pipeline — use `$autopilot`
- There is only one sequential task — delegate directly

## What It Provides

- **Parallelism**: Fire multiple agents simultaneously
- **Smart routing**: Route each task to the right model tier
- **Background execution**: Long operations run in background

## What It Does NOT Provide

- **Persistence**: Use `$ralph` for "don't stop until done"
- **Verification loops**: Use `$ralph` or `$ultraqa`
- **State management**: Use `$ralph` for resume capability

## Execution Policy

1. Fire all independent agent calls simultaneously
2. Always pass `model` parameter explicitly when delegating
3. Use `run_in_background: true` for operations over ~30 seconds
4. Run quick commands in foreground

## Task Classification

| Task Type | Tier | Example |
|-----------|------|---------|
| Simple lookups | LOW | Add type export |
| Standard implementation | STANDARD | Implement API endpoint |
| Complex analysis | THOROUGH | Major refactoring |

## Relationship to Other Modes

```
ralph (persistence wrapper)
  └── includes: ultrawork

autopilot (autonomous execution)
  └── includes: ralph
       └── includes: ultrawork

ecomode (token efficiency)
  └── modifies: ultrawork's model selection
```

## Keywords

- ultrawork, ulw, parallel
- run in parallel, concurrent
- multi-agent delegation
