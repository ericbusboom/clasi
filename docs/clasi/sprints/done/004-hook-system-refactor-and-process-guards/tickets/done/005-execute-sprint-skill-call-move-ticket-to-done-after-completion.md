---
id: '005'
title: 'Execute-sprint skill: call move_ticket_to_done after completion'
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
todo: execute-sprint-skill-move-tickets-to-done.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Execute-sprint skill: call move_ticket_to_done after completion

## Description

The `execute-sprint` skill (`clasi/plugin/skills/execute-sprint/SKILL.md`)
dispatches programmer tasks but does not include an explicit numbered step for
the team-lead to call `move_ticket_to_done(ticket_path)` after each programmer
task completes. The skill contains a strong block note about this requirement
but it reads as a caveat rather than a process step, making it easy to overlook.

This ticket adds an explicit numbered sub-step to the Monitor Progress section.
It also updates the installed copy in `.claude/skills/execute-sprint/SKILL.md`
so the currently active team-lead session picks up the fix without needing
`clasi init`.

This is a markdown-only change — no Python source code is modified.

## Acceptance Criteria

- [x] `clasi/plugin/skills/execute-sprint/SKILL.md` contains a numbered step
  (in or after "Monitor Progress") that explicitly calls
  `move_ticket_to_done(ticket_path)` for each completed programmer task
- [x] The step specifies that the team-lead (not the programmer) calls this
  MCP tool
- [x] The step specifies the ticket path format:
  `docs/clasi/sprints/NNN-slug/tickets/NNN-slug.md`
- [x] `.claude/skills/execute-sprint/SKILL.md` is updated to match
- [x] All existing tests pass (`uv run pytest`)

## Implementation Plan

### Approach

Edit `clasi/plugin/skills/execute-sprint/SKILL.md`. In the
`### 5. Monitor Progress` section, add a sub-step block after the existing
bullets. Then copy the updated content to the live `.claude/skills/` path.

### Files to Modify

**`clasi/plugin/skills/execute-sprint/SKILL.md`**:

In the `### 5. Monitor Progress` section, after "If a programmer fails after
repeated attempts, escalate to the stakeholder.", add:

```markdown
After each programmer Task completes successfully:
1. Verify `status: done` is set in the ticket's frontmatter.
2. Call `move_ticket_to_done(ticket_path)` where `ticket_path` is the relative
   path: `docs/clasi/sprints/NNN-slug/tickets/NNN-slug.md`.
   This is a team-lead responsibility — the programmer sets the frontmatter;
   the team-lead moves the file.
3. Continue monitoring remaining tasks.
```

The existing "Ticket completion is mandatory" block note may be retained as
reinforcement or removed to avoid duplication — either is acceptable.

**`.claude/skills/execute-sprint/SKILL.md`**:

Write the same updated content so the currently-installed skill is in sync.

### Testing Plan

- No unit tests required (markdown-only change).
- **Manual verification**: read the updated SKILL.md and confirm the numbered
  step is present, clear, and in the correct location within the workflow.
- **Existing tests**: `uv run pytest` — all must pass (no Python changes).

### Documentation Updates

The skill file is the documentation. No additional changes required.
