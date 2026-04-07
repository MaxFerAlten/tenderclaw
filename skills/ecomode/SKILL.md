---
name: ecomode
description: Token-efficient model routing modifier
---

# Ecomode Skill

Token-efficient model routing. This is a **MODIFIER**, not a standalone execution mode.

## What Ecomode Does

Overrides default model selection to prefer cheaper tiers:

| Default Tier | Ecomode Override |
|--------------|------------------|
| THOROUGH | STANDARD, THOROUGH only if essential |
| STANDARD | LOW first, STANDARD if needed |
| LOW | LOW - no change |

## Combining with Other Modes

Ecomode combines with execution modes:

| Combination | Effect |
|-------------|--------|
| `eco ralph` | Ralph loop with cheaper agents |
| `eco ultrawork` | Parallel with cheaper agents |
| `eco autopilot` | Full autonomous with cost optimization |

## Routing Rules

**ALWAYS prefer lower tiers. Only escalate when genuinely required.**

| Decision | Rule |
|----------|------|
| DEFAULT | Start with LOW tier for most tasks |
| UPGRADE | Escalate to STANDARD when LOW fails |
| AVOID | THOROUGH - only for planning if essential |

## Agent Selection

Ecomode preference order:

```
// PREFERRED - Use for most tasks
delegate(role="executor", tier="LOW", task="...")
delegate(role="explore", tier="LOW", task="...")

// FALLBACK - Only if LOW fails
delegate(role="executor", tier="STANDARD", task="...")

// AVOID - Only for planning/critique
delegate(role="planner", tier="THOROUGH", task="...")
```

## Token Savings Tips

1. Batch similar tasks to one agent
2. Use explore (LOW) for file discovery
3. Prefer LOW-tier for simple changes
4. Use writer (LOW) for documentation
5. Avoid THOROUGH unless essential

## State Management

```
State: ecomode
  - active: boolean
```

## Keywords

- eco, ecomode, save tokens
- cost efficient, cheap mode
