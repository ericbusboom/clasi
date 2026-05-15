---
id: '001'
title: Sprint-Scoped Issue Lifecycle
status: planning-docs
branch: sprint/001-sprint-scoped-issue-lifecycle
todos:
  - plan-sprint-scoped-issue-lifecycle-sprint-issues-done-split-close-gate.md
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001: Sprint-Scoped Issue Lifecycle

## Goals

1. Make `Issue.move_to_done()` physically relocate the issue file into `<sprint>/issues/done/`, mirroring the existing `Ticket.move_to_done` behavior.
2. Add `Sprint.issues_done_dir` property and update `Sprint.list_issues` and `Project.get_issue` to look in both `issues/` and `issues/done/`.
3. Add a `split_issue` MCP tool for partial-scope issues during sprint planning.
4. Update the close-sprint precondition self-repair to walk `<sprint>/issues/done/`, migrate legacy top-level done files, and relocate pending-pool done-tagged issues into the sprint done directory.
5. Update `issue`, `plan-sprint`, `create-tickets`, and `close-sprint` skill docs to describe the new lifecycle.
6. Add tests covering new behavior and legacy migration.

## Problem

The issue lifecycle is inconsistent with the ticket lifecycle. `Ticket.move_to_done` physically moves the file into `tickets/done/` — this is a state invariant (the ticket machine's `done` state requires `is_ticket_in_done_dir`). `Issue.move_to_done` only flips frontmatter; the file never moves. This means the close-sprint precondition log message claims "moved TODO ... to done/" but nothing actually moves. There is also no first-class mechanism to split an issue when only part of its scope fits in a sprint, and the skill docs don't describe the sprint-scoped issue lifecycle at all.

## Solution

Rewrite `Issue.move_to_done` to mirror `Ticket.move_to_done` exactly: check if already in `done/` (idempotent), otherwise `mkdir` + `rename` + reattach `Artifact`. Add `Sprint.issues_done_dir` and update `Sprint.list_issues` / `Project.get_issue` to scan both directories. Update close-sprint self-repair to handle the new layout plus two legacy scenarios. Add `split_issue` MCP tool. Update four skill docs.

## Success Criteria

- `Issue.move_to_done()` on a sprint-scoped issue moves the file to `<sprint>/issues/done/<filename>`.
- Calling `move_to_done()` a second time is a no-op (idempotent).
- `Sprint.list_issues()` returns issues from both `issues/` and `issues/done/`.
- `Project.get_issue(filename)` resolves filenames in `<sprint>/issues/done/`.
- `close_sprint` self-repair handles: (a) done files still at `issues/` top-level, (b) pending-pool done-tagged issues for the sprint.
- `split_issue` MCP tool creates a sibling file with correct cross-link frontmatter.
- All new and updated unit tests pass.
- All existing tests pass (updated where behavior changes).

## Scope

### In Scope

- `clasi/issue.py`: rewrite `move_to_done`.
- `clasi/sprint.py`: add `issues_done_dir`, extend `list_issues`.
- `clasi/project.py`: extend `get_issue` to check `<sprint>/issues/done/`.
- `clasi/tools/artifact_tools.py`: add `split_issue` tool; update close-sprint precondition pass in both `_close_sprint_full` and `_close_sprint_legacy`.
- `clasi/plugin/skills/issue/SKILL.md`: add split guidance.
- `.claude/skills/plan-sprint/SKILL.md`, `.claude/skills/create-tickets/SKILL.md`, `.claude/skills/close-sprint/SKILL.md`: workflow updates.
- `tests/unit/test_issue.py`, `test_issue_lifecycle.py`, `test_issue_tools.py`, `test_artifact_tools.py`: new and updated tests.

### Out of Scope

- The `move_issue_to_done` MCP tool body (no change needed — it calls `issue.move_to_done()` which will now do the right thing automatically).
- The `_todo_is_deferred` helper (no change required).
- Phase-DB changes.
- UI or web frontend changes.

## Test Strategy

Unit tests for each changed module. Existing tests that assert the old "file stays in place" behavior will be updated to assert the new "file moves to done/" behavior. New tests cover: `issues_done_dir` property, `list_issues` scanning both dirs, `get_issue` resolving done-dir files, idempotent `move_to_done`, `split_issue` cross-links, close-sprint legacy migration scenarios.

## Architecture Notes

The key architectural principle is that **physical file location is a state invariant** for both tickets and issues. An issue in `done/` is unambiguously done without reading frontmatter. This mirrors the ticket machine's `is_ticket_in_done_dir` invariant and makes the system's state checkable by directory listing alone.

The `move_issue_to_done` MCP tool currently validates that the issue is in `<sprint>/issues/` before accepting a `sprint_id` argument. After this sprint, the tool's location check must be relaxed to also accept `<sprint>/issues/done/` (idempotent case). This is handled in T1 as part of updating `get_issue` and adjusting the location guard in `move_issue_to_done`.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Issue.move_to_done file relocation + Sprint.issues_done_dir + lookups | — |
| 002 | Close-sprint precondition: done-dir awareness + legacy migration | 001 |
| 003 | split_issue MCP tool + tests | 001 |
| 004 | Skill doc updates | 003 |

Tickets execute serially in the order listed.
