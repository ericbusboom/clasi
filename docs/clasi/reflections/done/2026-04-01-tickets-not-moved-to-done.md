---
date: 2026-04-01
sprint: 001
category: missing-instruction
---

# What Happened

All 3 tickets in sprint 001 were implemented and had their frontmatter set to
`status: done`, but the files were never physically moved from `tickets/` to
`tickets/done/`. The `move_ticket_to_done` MCP tool was never called.

# What Should Have Happened

After each programmer completed a ticket, the orchestrator should have called
`move_ticket_to_done` to move the ticket file (and plan, if any) into the
`tickets/done/` directory and committed the move.

# Root Cause

**Missing instruction in `execute-sprint` skill.**

The responsibility chain is deliberately split:

- **Programmer agent** (`programmer/agent.md`): implements the ticket, updates
  frontmatter to `status: done`, but is explicitly told NOT to move files.
- **Sprint-executor controller** (`sprint-executor/agent.md`, step 3.h):
  validates work and calls `move_ticket_to_done`.

However, the **`execute-sprint` skill** (`SKILL.md`) — which is what the
team-lead actually invokes — never references the sprint-executor agent or the
`move_ticket_to_done` tool. Its flow is:

1. Read tickets → order by dependencies → create Tasks
2. Spawn **programmer** agents (not sprint-executor)
3. Monitor progress
4. Close sprint

Between steps 2–4, there is no step that moves completed tickets. The
`TaskCompleted` hook (step 4, lines 58–62) validates frontmatter and merges
the worktree branch, but does not move the ticket file.

The sprint-executor agent has the correct instructions, but the execute-sprint
skill bypasses it entirely — it dispatches programmers directly. The move
responsibility falls through the gap.

# Proposed Fix

Add a step to `execute-sprint/SKILL.md` between "Monitor Progress" and
"Close Sprint":

> ### 5b. Move Completed Tickets
>
> After each programmer's task completes and the worktree merges back:
> 1. Call `move_ticket_to_done(path)` for the ticket file
> 2. Commit the move: `chore: move ticket #NNN to done`

Alternatively, add the move to the `TaskCompleted` hook definition (lines
58–62) so it happens as part of the merge-back validation.
