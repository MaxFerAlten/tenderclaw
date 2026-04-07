---
name: worker
description: Team worker protocol (ACK, mailbox, task lifecycle) for tmux-based teams
---

# Worker Skill

Protocol for a Codex session that was started as an OMX Team worker (a tmux pane spawned by `$team`).

## Identity

You MUST be running with `OMX_TEAM_WORKER` set. It looks like:

`<team-name>/worker-<n>`

Example: `alpha/worker-2`

## Startup Protocol (ACK)

1. Parse `OMX_TEAM_WORKER` into:
   - `teamName` (before the `/`)
   - `workerName` (after the `/`, usually `worker-<n>`)

2. Send a startup ACK to the lead mailbox **before task work**:
   - Recipient: `leader-fixed`
   - Body: `ACK: <workerName> initialized`

## Inbox + Tasks

1. Resolve team state root (in order):
   - `OMX_TEAM_STATE_ROOT` env
   - Worker identity `team_state_root`
   - Team config `team_state_root`
   - Local fallback (`.omx/state`)

2. Read your inbox:
   `<team_state_root>/team/<teamName>/workers/<workerName>/inbox.md`

3. Pick the first unblocked task assigned to you

4. Read the task file:
   `<team_state_root>/team/<teamName>/tasks/task-<id>.json`

5. Claim the task (do NOT start work without a claim)

6. Do the work

7. Complete/fail the task via lifecycle transition

8. Update worker status with `{"state":"idle", ...}`

## Mailbox

Check your mailbox for messages:
`<team_state_root>/team/<teamName>/mailbox/<workerName>.json`

When notified, read messages and follow instructions.

## Dispatch Discipline

- Prefer inbox/mailbox/task state operations
- Do NOT rely on ad-hoc tmux keystrokes as primary channel
- If manual trigger arrives, re-check state and continue through normal lifecycle

## Shutdown

If the lead sends a shutdown request:
1. Follow shutdown inbox instructions exactly
2. Write shutdown ack file
3. Exit the Codex session
