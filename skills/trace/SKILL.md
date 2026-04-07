---
name: trace
description: Show agent flow trace timeline and summary
---

# Trace Skill

[TRACE MODE ACTIVATED]

Display the flow trace showing how hooks, keywords, skills, agents, and tools interacted during this session.

## When to Use

This skill activates when:
- User wants to understand session flow
- Debugging complex interactions
- User says "trace", "show trace", "flow timeline"

## Instructions

### 1. Timeline
Show the chronological event timeline:
- Hook fire counts
- Keywords detected
- Skills activated
- Mode transitions
- Tool usage

### 2. Summary
Show aggregate statistics:
- Event counts by type
- Performance metrics
- Bottleneck identification
- Flow patterns

## Output Format

Present the timeline first, then the summary. Highlight:

- **Mode transitions** - How execution modes changed
- **Bottlenecks** - Slow tools or agents
- **Flow patterns** - Keyword → Skill → Agent chains

## Example Output

```
TIMELINE
---------
10:01:23 [keyword] "ralph" detected → ralph mode activated
10:01:24 [mode] Entered ralph execution loop
10:01:30 [agent] executor started: Implement feature X
10:02:45 [tool] bash: npm test → 12 passed
10:03:12 [mode] Ralph verification: PASS
10:03:13 [mode] Exited ralph mode

SUMMARY
-------
Keywords detected: 1 (ralph)
Modes entered: 1 (ralph)
Agents spawned: 1 (executor)
Tools called: 8
Total duration: 2m 15s

Bottlenecks: None detected
Flow: keyword → mode → agent → tool → verification
```

## Keywords

- trace, show trace, flow trace
- timeline, event log
- audit trail, execution trace
