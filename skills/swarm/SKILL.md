---
name: swarm
description: N coordinated agents on shared task list (compatibility facade over team)
---

# Swarm Skill (Compatibility Facade)

Swarm is a compatibility alias for the `/team` skill.

## Usage

```
/swarm N:agent-type "task description"
/swarm "task description"
```

## Behavior

This skill is identical to `/team`. All swarm invocations are routed to the Team skill.

Invoke the Team skill with the same arguments:

```
/team <arguments>
```

Follow the Team skill's full documentation for:
- Staged pipeline
- Agent routing
- Coordination semantics

## Keywords

- swarm, swarming
- parallel agents, coordinated agents
- multi-agent

## See Also

- `$team` - Primary skill documentation
