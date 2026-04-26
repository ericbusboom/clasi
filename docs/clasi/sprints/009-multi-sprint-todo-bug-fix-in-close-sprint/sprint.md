---
id: "009"
title: "Multi-Sprint TODO Bug Fix in close_sprint"
status: roadmap
branch: sprint/009-multi-sprint-todo-bug-fix-in-close-sprint
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 009: Multi-Sprint TODO Bug Fix in close_sprint

## Goals

- Fix `close_sprint` (and `move_ticket_to_done`) so that umbrella / multi-sprint TODO files are not archived to `done/` when only the first sprint's tickets complete.
- Implement the preferred fix: an opt-in `completes_todo` frontmatter flag on tickets (default `true`) that controls whether closing a ticket triggers TODO archival.

## Scope

### In Scope

- Add `completes_todo: true|false` (default `true`) per linked TODO filename to ticket YAML frontmatter.
- Update `move_ticket_to_done` to respect the flag — only move a linked TODO to `done/` when `completes_todo` is `true` for that link.
- Update `close_sprint` to apply the same logic when it auto-moves TODOs.
- Update `create_ticket` MCP tool (and template) so the new field is documentable and settable.
- Add or update tests covering single-sprint TODO archival (still works), multi-sprint TODO preservation (new flag), and backward-compatible default.

### Out of Scope

- Alternative fix strategies (opt-in on TODO frontmatter, explicit TODO-close step, cross-sprint heuristic).
- Changes to other `close_sprint` behavior (test command, version bump, archive, etc.).
- Changes unrelated to multi-sprint TODO tracking.

## TODO References

Source TODO: `docs/clasi/todo/clasi-bug-multi-sprint-todos.md`

## Sequencing Note

Sprint 009 is a self-contained bug fix with no dependency on sprint 008 or 010. It is sequenced after 008 (which removes dead code) and before 010 (which adds a new feature) to keep the change surface clean and reviewable in isolation. It could ship in any order without conflict.

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
