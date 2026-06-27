---
id: '014'
title: Issue-ticket linkage and done lifecycle
status: planning-docs
branch: sprint/014-issue-ticket-linkage-and-done-lifecycle
use-cases: []
issues:
- issue-done-and-linkage-front-matter-not-updated.md
- gh-12-ensure-all-tickets-that-implment-a-todo-are-linked.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 014: Issue-ticket linkage and done lifecycle

## Goals

Ensure issues are bidirectionally linked to sprints and tickets in front matter, and
are swept to `done/` at sprint close. After this sprint, the full issue lifecycle
fires automatically: an issue created, linked to a sprint, attached to a ticket, and
resolved moves to `<sprint>/issues/done/` at close — with unresolved issues reported
non-blocking rather than blocking closure.

## Problem

The issue → sprint → ticket → done chain is architecturally complete but never fires
in practice because agents don't invoke the linkage tools. Three root defects:

1. **Agents are never instructed to link.** `sprint-roadmap`, `plan-sprint`, and
   `team-lead` skill/agent docs don't tell agents to call `link_sprint_issues`,
   `create_ticket(issue=)`, or `add_issue_ref`. The tools exist (added in sprint 002)
   but nothing invokes them.
2. **`create_ticket` auto-link field mismatch** (`clasi/tools/artifact_tools.py:612`):
   auto-link reads the sprint's `todos` field, but `link_sprint_issues` writes `issues:`.
   So even a correctly-linked roadmap never auto-attaches issues to tickets.
3. **`_close_sprint_full` blocks on unresolved issues** while `_close_sprint_legacy`
   does not. The two paths diverged; the full path should mirror the legacy path:
   collect `unresolved_issues`, add to result, continue.

## Solution

### Code changes (`clasi/tools/artifact_tools.py`)

- **A1.** Fix `create_ticket` auto-link: read `issues` field first, fall back to `todos`
  for legacy sprint compatibility (line ~612).
- **A2.** Make `_close_sprint_full` non-blocking on unresolved issues (lines ~1256-1276):
  mirror the legacy path — collect `unresolved_issues`, add to success result, continue.

### Skill/agent doc changes (source of truth: `clasi/plugin/...`)

- **B1.** `clasi/plugin/skills/sprint-roadmap/SKILL.md` (~45-46): instruct calling
  `link_sprint_issues(sprint_id, [filenames])` for every issue claimed in the roadmap.
- **B2.** `clasi/plugin/skills/plan-sprint/plan-sprint.md` (~53-57): call
  `link_sprint_issues` explicitly (not manual `write_artifact_frontmatter`).
- **B3.** `clasi/plugin/skills/create-tickets/create-tickets.md`: verify and lightly
  reinforce that tickets carry `issue:` back-refs via `create_ticket(issue=)` and
  `add_issue_ref`.
- **B4.** `clasi/plugin/agents/team-lead/agent.md`: add "Issue lifecycle" responsibility —
  link at roadmap, ensure tickets carry `issue:` back-refs, confirm resolved issues swept
  at close and mop up `unresolved_issues`.
- **B5.** `clasi/plugin/skills/close-sprint/SKILL.md` (~56-70): document the auto-sweep
  and non-blocking `unresolved_issues` report; instruct mopping up afterward.

Note: skill/agent docs in `.claude/` and `.agents/` are installer-generated copies.
All edits must target `clasi/plugin/skills/` and `clasi/plugin/agents/` only.

## Success Criteria

- `create_ticket` auto-link reads `issues:` field (with `todos:` fallback).
- `_close_sprint_full` closes successfully when unresolved issues are present; result
  includes `unresolved_issues` list.
- Skill/agent docs in `clasi/plugin/...` instruct agents to invoke all linkage steps.
- `pytest tests/unit/test_sweep_done_issues.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_mcp_server.py -q` green, with new cases for A1 and A2.
- End-to-end: create issue → `link_sprint_issues` → `create_ticket(issue=)` →
  `move_ticket_to_done` → issue swept to `<sprint>/issues/done/` with `status: done`;
  `close_sprint` with unresolved issue closes and reports `unresolved_issues`.

## Scope

### In Scope

- `clasi/tools/artifact_tools.py` — `create_ticket` auto-link field fix; `_close_sprint_full` non-blocking fix
- `clasi/plugin/skills/sprint-roadmap/SKILL.md`
- `clasi/plugin/skills/plan-sprint/plan-sprint.md`
- `clasi/plugin/skills/create-tickets/create-tickets.md`
- `clasi/plugin/skills/close-sprint/SKILL.md`
- `clasi/plugin/agents/team-lead/agent.md`
- Tests for the above fixes

### Out of Scope

- The physical issue-move design itself (confirmed: keep as-is)
- `gh-12` is subsumed by `issue-done-and-linkage-front-matter-not-updated.md` (the B-series
  doc fixes are the correct fix for what gh-12 describes)

## Architecture Notes

The linkage chain is already architecturally correct. This sprint is a precision fix:
repair the one field-name bug and harden the close path, then install the missing
instructions so agents actually invoke the tools.

## Dependencies

After sprint 012. (The state-machine path fixes unblock phase gates that the linkage
workflows depend on.)

## Issues Addressed

- `issue-done-and-linkage-front-matter-not-updated.md` (primary, contains detailed implementation plan)
- `gh-12-ensure-all-tickets-that-implment-a-todo-are-linked.md` (subset/overlap — subsumed by the doc fixes above)

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Fix create_ticket auto-link to read issues: field | — |
| 002 | Fix _close_sprint_full to be non-blocking on unresolved issues | — |
| 003 | Add unit tests for auto-link field fix and non-blocking close | 001, 002 |
| 004 | Update sprint-roadmap and plan-sprint skill docs with linkage instructions | 003 |
| 005 | Update create-tickets, team-lead, and close-sprint docs with lifecycle instructions | 004 |

Tickets execute serially in the order listed.
