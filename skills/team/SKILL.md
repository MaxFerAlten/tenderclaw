---
name: team
description: N coordinated agents on shared task list with team pipeline
trigger: team
---

# Team Skill

Team mode coordinates multiple agents on a shared task list with structured pipeline.

## Pipeline
team-plan → team-prd → team-exec → team-verify → team-fix

## When to Use
- Multi-agent coordination needed
- Parallel execution improves throughput
- Task can be split into independent subtasks

## Team Composition
- **Planner**: Creates task breakdown
- **Executor**: Implements features
- **Verifier**: Runs tests and verification
- **Architect**: Reviews quality

## State Management
Team state stored in `.tenderclaw/state/team/{team-name}/`:
- `config.json` - Team configuration
- `manifest.json` - Team manifest
- `tasks/task-{id}.json` - Task definitions
- `workers/worker-{n}/` - Worker state

## Execution Flow
1. Create team and task list
2. Assign tasks to workers
3. Monitor progress
4. Collect results
5. Verify completion
6. Shutdown team

## Lifecycle Commands
- Start team with N workers
- Monitor via status endpoint
- Shutdown when complete
