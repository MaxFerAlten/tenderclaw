# Team Execution Protocol

## Team Setup
1. Create team manifest
2. Break task into N subtasks
3. Assign to available agents
4. Set up shared state

## Worker Protocol
Workers should:
- Report progress to shared state
- Check inbox for new tasks
- Commit changes on completion
- Report to leader on finish

## Coordination
Leader coordinates via:
- Task state in `.tenderclaw/state/team/`
- Worker inbox files
- Progress polling

## Completion Gate
- pending=0
- in_progress=0
- failed=0

Only then shutdown team.
