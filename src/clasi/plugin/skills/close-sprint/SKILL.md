---
name: close-sprint
description: Validates and closes a completed sprint — verifies tickets, merges branch, archives sprint
---

Closes a completed sprint by invoking the close_sprint MCP tool, which merges the branch, archives the sprint directory, bumps the version, and pushes tags.

`close_sprint()` with no arguments auto-detects the sprint from the current git branch (`sprint/NNN-*`). The `sprint_id` parameter is optional — omit it when already on the sprint branch. Provide it explicitly in scripted or CI contexts.

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

## Worktree Pruning at Close

As the final step of `close_sprint`, the tool prunes any git worktrees
associated with the closing sprint branch. This is a cleanup safety net for
worktrees left behind by other tooling (e.g. a manually created worktree, or
one left over from an interrupted session) — sprint execution itself never
creates a worktree per ticket; `acquire_execution_lock` only acquires the
sprint's execution lock and does not touch worktrees at all. This step's
scope is unrelated to how many tickets the sprint ran.

The result JSON includes a `worktrees_pruned` list of absolute paths removed.
If any removal failed, a `worktrees_failed` list is also present and the
failure is appended to `repairs`. A failed worktree removal does not abort the
close — the sprint is still archived successfully.
