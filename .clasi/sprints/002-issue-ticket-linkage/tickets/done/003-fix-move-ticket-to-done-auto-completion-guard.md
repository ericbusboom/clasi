---
id: '003'
title: Fix move_ticket_to_done auto-completion guard
status: done
use-cases:
- SUC-003
- SUC-004
depends-on:
- '001'
github-issue: ''
issue:
- auto-completion-fragility-in-move-ticket-to-done.md
- propagate-issue-refs-across-sprint-tickets.md
completes_issue:
  auto-completion-fragility-in-move-ticket-to-done.md: true
  propagate-issue-refs-across-sprint-tickets.md: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix move_ticket_to_done auto-completion guard

## Description

Wire `_sweep_done_issues(sprint)` (created in ticket 001) into
`move_ticket_to_done` and into `_close_sprint_full`, replacing the faulty
guarded auto-completion block.

**The bug:** In `move_ticket_to_done` (artifact_tools.py:719-742), the
auto-completion block is guarded by `if todo_refs is not None:`. When the
moved ticket has no `issue:` frontmatter ref, the block never runs — even if
completing that ticket was the final step needed to complete an issue. This
caused the sprint 001 post-mortem scenario where T2-T4 (no `issue:` ref)
could not trigger issue auto-completion.

**The fix:** Replace the entire guarded block (lines 719-742) with a single
call to `_sweep_done_issues(sprint)`. Populate `result["completed_todos"]`
from the return value if non-empty. Also call `_sweep_done_issues` at the
start of the `_close_sprint_full` step 1b precondition pass as a self-repair
step, before the hard-fail check.

## Acceptance Criteria

- [x] `move_ticket_to_done` no longer contains the `if todo_refs is not None:`
      guard; the auto-completion block is replaced with
      `_sweep_done_issues(sprint)`.
- [x] After moving the **last** ticket that completes an issue (regardless of
      whether that ticket has `issue:` ref), the issue is auto-moved to
      `<sprint>/issues/done/` with `status: done`.
- [x] `result["completed_todos"]` is populated with the list of completed
      issue filenames when any issues were swept.
- [x] `completes_issue: false` on any sprint ticket still suppresses
      auto-completion (behavior preserved via `_sweep_done_issues`).
- [x] Idempotent: calling `move_ticket_to_done` when the issue is already done
      does not error.
- [x] `_close_sprint_full` step 1b calls `_sweep_done_issues(sprint)` as the
      first action, before the existing hard-fail scan.
- [x] Existing happy-path test (single ticket with `issue:` ref → move →
      issue done) still passes.
- [x] Sprint 001 scenario: T1 has `issue:` ref, T2-T4 do not; after moving T4
      to done, the issue is in `<sprint>/issues/done/`.

## Implementation Plan

### Approach

In `move_ticket_to_done`:
1. Remove lines 719-742 (the `if todo_refs is not None:` block).
2. After `result = ticket.move_to_done_with_plan()`, add:
   ```python
   completed = _sweep_done_issues(sprint)
   if completed:
       result["completed_todos"] = completed
   ```

In `_close_sprint_full` step 1b (~line 985):
1. Before the existing `sprint_issues_dir_full.exists()` block, add:
   ```python
   _sweep_done_issues(sprint)
   ```
   (Return value discarded — the sweep is a self-repair step; the existing
   scan handles reporting and hard-fail.)

### Files to modify

- `clasi/tools/artifact_tools.py`:
  - `move_ticket_to_done`: replace guarded block with `_sweep_done_issues`.
  - `_close_sprint_full`: insert `_sweep_done_issues(sprint)` call at start
    of step 1b.

### Testing plan

- **Existing tests to run**: `uv run pytest tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_artifact_tools.py`
- **New tests to write** (in `tests/unit/test_issue_lifecycle.py`):
  - Sprint 001 scenario: T1 has `issue:` ref, T2-T4 do not. Issue's `tickets:`
    lists all four. After moving T4 to done (all done), issue is in
    `<sprint>/issues/done/`.
  - Existing single-ticket happy-path still passes.
  - `completed_todos` key present in return JSON when issue is completed.
  - `completed_todos` key absent from return JSON when no issue is completed.
  - `completes_issue: false` scenario: moving last ticket does not auto-complete.
- **Verification command**: `uv run pytest`

### Documentation updates

None. Skill doc updates are in ticket 005.
