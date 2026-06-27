---
name: close-sprint
description: Validates and closes a completed sprint — verifies tickets, merges branch, archives sprint
---

Closes a completed sprint by invoking the close_sprint MCP tool, which merges the branch, archives the sprint directory, bumps the version, and pushes tags.

## Instructions

Load from: `clasi/schemas/se-process/instructions/close.md`

## Issue Sweep at Close

When `close_sprint` runs, it automatically calls `_sweep_done_issues`, which
moves any resolved sprint issues from `<sprint>/issues/` to
`<sprint>/issues/done/`. No manual `move_issue_to_done` call is needed for
issues whose tickets are all done.

If any sprint issues remain unresolved at close, the close still succeeds.
The result JSON will contain an `unresolved_issues` list with the filenames.
Read this list and surface it to the team-lead for mop-up — these issues were
not resolved in the sprint and need follow-up.
