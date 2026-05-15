---
id: '001'
title: Extract _sweep_done_issues shared helper
status: done
use-cases:
- SUC-003
- SUC-004
depends-on: []
github-issue: ''
issue:
- auto-completion-fragility-in-move-ticket-to-done.md
- propagate-issue-refs-across-sprint-tickets.md
- sprint-todo-bidirectional-links.md
completes_issue:
  auto-completion-fragility-in-move-ticket-to-done.md: false
  propagate-issue-refs-across-sprint-tickets.md: false
  sprint-todo-bidirectional-links.md: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extract _sweep_done_issues shared helper

## Description

Extract the auto-completion sweep logic from `move_ticket_to_done` into a
reusable module-level helper `_sweep_done_issues(sprint)`. This is the
foundational change that the auto-completion fix (ticket 003) depends on.

Currently the auto-completion logic in `move_ticket_to_done` (lines 719-742)
is guarded by `if todo_refs is not None:` — meaning it only runs when the
moved ticket itself has an `issue:` frontmatter ref. The equivalent sweep
logic in `_close_sprint_full` (lines 985-1044) runs unconditionally but is
inline and duplicated. This ticket creates the shared helper only; wiring it
in is ticket 003.

## Acceptance Criteria

- [x] `_sweep_done_issues(sprint: Sprint) -> list[str]` exists as a
      module-level function in `clasi/tools/artifact_tools.py`, placed near
      the other private utility functions (`_is_ticket_done`,
      `_any_ticket_suppresses_todo`, `_todo_is_deferred`).
- [x] Scans sprint-scoped issues: `<sprint>/issues/*.md` where
      `issue.sprint == sprint.id` and `issue.status == "in-progress"`.
- [x] Scans pending-pool issues: `project.issues_dir/*.md` where
      `issue.sprint == sprint.id` and `issue.status == "in-progress"`.
- [x] For each in-progress issue, checks `_is_ticket_done` for every entry
      in `issue.tickets`. If all done and list non-empty, calls
      `_any_ticket_suppresses_todo`; if not suppressed, completes the issue.
- [x] For sprint-scoped issues: calls `issue.move_to_done()` directly.
- [x] For pending-pool issues: applies the two-step relocation pattern —
      (a) computes target `<sprint>/issues/done/<filename>`, (b) `mkdir`,
      (c) renames file, (d) reattaches `issue._artifact = Artifact(target)`,
      (e) calls `issue.move_to_done()` for frontmatter only. (See sprint 001
      architecture-update.md §4 "Pending-pool scan". Alternatively, add a
      `target_dir` parameter to `Issue.move_to_done` if judged cleaner.)
- [x] Returns the list of issue filenames completed in the sweep.
- [x] Idempotent: issues already in `issues/done/` are not in-progress and
      are naturally skipped by the scan — no error on repeat calls.

## Implementation Plan

### Approach

New function placed in the utility section of `artifact_tools.py` near the
other `_` helpers (~line 155). The function body is largely extracted from
the existing inline block at lines 719-742 and the pending-pool section of
`_close_sprint_full` at lines 1035-1044, with the `if todo_refs is not None:`
guard removed.

### Files to modify

- `clasi/tools/artifact_tools.py` — add `_sweep_done_issues` function.
- `clasi/issue.py` — optionally add `target_dir` parameter to
  `Issue.move_to_done` to simplify pending-pool relocation.

### Testing plan

- **Existing tests to run**: `uv run pytest tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_issue.py`
- **New tests to write** (in `tests/unit/test_issue_lifecycle.py` or a new
  `tests/unit/test_sweep_done_issues.py`):
  - Sprint with one in-progress sprint-scoped issue, all its tickets done →
    sweep returns `[filename]`, file is in `<sprint>/issues/done/`.
  - Sprint with a pending-pool issue (`sprint:` field set), all tickets done →
    sweep physically relocates to `<sprint>/issues/done/`.
  - Sprint issue with `completes_issue: false` on a ticket → issue not moved,
    returns `[]`.
  - Issue already in `done/` → no error, not included in sweep results.
  - Issue with no `tickets:` entries → not completed (list is empty, condition
    `all_done and ref_tickets` is False).
- **Verification command**: `uv run pytest`

### Documentation updates

None for this ticket. Skill doc updates are in ticket 005.
