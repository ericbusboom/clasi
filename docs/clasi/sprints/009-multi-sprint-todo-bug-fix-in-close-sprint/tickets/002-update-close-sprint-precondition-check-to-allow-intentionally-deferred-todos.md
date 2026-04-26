---
id: "002"
title: "Update close_sprint precondition check to allow intentionally deferred TODOs"
status: todo
use-cases:
  - SUC-002
depends-on:
  - 009-001
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update close_sprint precondition check to allow intentionally deferred TODOs

## Description

`_close_sprint_full` (step 1b) blocks sprint close if any in-progress TODO is associated with the sprint. For multi-sprint umbrella TODOs this is a false error: the TODO is still in-progress intentionally because future sprints will consume the remaining scope. The fix: if every ticket in the sprint that references a given in-progress TODO has `completes_todo: false` for that filename, the precondition check skips that TODO instead of raising an error.

The same pattern applies to `_close_sprint_legacy` which has an analogous TODO block.

This ticket depends on 009-001 because it calls `Ticket.completes_todo_for`.

## Acceptance Criteria

- [ ] `_close_sprint_full` step 1b does not raise an error for an in-progress TODO when at least one ticket in the sprint has `completes_todo: false` for that TODO filename
- [ ] `_close_sprint_full` step 1b still raises an error for an in-progress TODO when all linked tickets in the sprint have `completes_todo: true` (or absent) — i.e., the TODO should have been archived but was not
- [ ] `_close_sprint_legacy` receives the same guard (parallel code path)
- [ ] The repair path (step 1b self-repair: `todo.status in ("done", "complete", "completed")`) is unaffected — TODOs that are already marked done are still moved
- [ ] TODOs not referenced by any ticket in the sprint are unaffected

## Implementation Plan

### Approach

In `_close_sprint_full` step 1b (lines ~816-847 of `artifact_tools.py`), before reporting an "unresolved" error for an in-progress TODO, load the sprint's tickets and check whether any ticket has `completes_todo: false` for the TODO filename. If so, continue (skip this TODO). Otherwise, proceed with the existing error return.

Implement a helper `_todo_is_deferred(sprint, todo_filename) -> bool` to avoid duplicating this logic between the `_close_sprint_full` and `_close_sprint_legacy` paths. The helper:
1. Gets all tickets in the sprint (from `sprint.tickets_dir` and `sprint.tickets_done_dir`)
2. For each ticket that lists `todo_filename` in its `todo` field, calls `ticket.completes_todo_for(todo_filename)`
3. Returns `True` if any such ticket returns `False` (meaning the TODO is intentionally deferred)

### Files to Modify

- `clasi/tools/artifact_tools.py`:
  - Add `_todo_is_deferred(sprint: Sprint, todo_filename: str) -> bool` function
  - In `_close_sprint_full` step 1b: before the error return for an unresolved in-progress TODO, call `_todo_is_deferred`; if it returns `True`, `continue` rather than returning an error
  - In `_close_sprint_legacy`: same guard around the analogous TODO block

### Key Implementation Detail

The deferred check must be scoped to the current sprint's tickets only. A TODO linked by tickets from a different sprint should not affect this sprint's close. Use `sprint.tickets_dir` and `sprint.tickets_done_dir` (both active and already-done tickets in this sprint) when iterating.

### Testing Plan

Add tests to `tests/unit/test_todo_tools.py` in a new or existing class:

1. `test_close_sprint_allows_deferred_todo` — sprint with one ticket referencing an in-progress TODO with `completes_todo: false`; `close_sprint` succeeds
2. `test_close_sprint_blocks_unresolved_todo` — sprint with one ticket referencing an in-progress TODO with `completes_todo: true` (or absent) and ticket is done but TODO was not archived (degenerate state); `close_sprint` returns error
3. `test_close_sprint_legacy_allows_deferred_todo` — same for the legacy path (no branch_name supplied)

### Verification Command

`uv run pytest tests/unit/test_todo_tools.py -x`
