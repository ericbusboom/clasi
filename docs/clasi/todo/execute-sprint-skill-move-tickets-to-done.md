---
status: pending
---

# Execute-sprint skill should move tickets to done after programmer completes

From reflection 2026-04-01-tickets-not-moved-to-done.md: the `execute-sprint` skill
dispatches programmers directly but has no step to call `move_ticket_to_done` after
each programmer completes. The programmer sets frontmatter to `status: done` but is
not responsible for moving the file. The team-lead currently does this manually.

Add a step to `clasi/plugin/skills/execute-sprint/SKILL.md` between "Monitor
Progress" and "Close Sprint": after each programmer's task completes, call
`move_ticket_to_done(path)` for the ticket file.

Alternatively, add the move to the `TaskCompleted` hook so it happens automatically
as part of the merge-back validation.
