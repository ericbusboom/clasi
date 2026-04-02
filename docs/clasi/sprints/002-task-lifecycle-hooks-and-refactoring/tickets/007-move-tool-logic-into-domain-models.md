---
id: '007'
title: Move tool logic into domain models
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: move-tool-logic-into-domain-models.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Move tool logic into domain models

## Description

Move business logic from MCP tool functions into domain model classes (Ticket, Sprint),
so tool functions become thin glue code that delegates to domain methods.

## Acceptance Criteria

- [x] `Ticket.move_to_done_with_plan()` method moves ticket file and optional plan file to done/
- [x] `Ticket.reopen()` method moves ticket back from done/, resets status, moves plan file back
- [x] `Sprint.ticket_counts()` method returns {todo, in_progress, done} counts
- [x] `Sprint.archive()` method updates status, copies architecture-update, moves to sprints/done/
- [x] `move_ticket_to_done` tool delegates plan-file move to `Ticket.move_to_done_with_plan()`
- [x] `reopen_ticket` tool delegates all logic to `Ticket.reopen()`
- [x] `get_sprint_status` tool uses `Sprint.ticket_counts()` instead of inline loop
- [x] `_close_sprint_legacy` uses `Sprint.archive()` for archival step
- [x] `_close_sprint_full` uses `Sprint.archive()` for archival step
- [x] All existing tests pass (856 passing)
- [x] New unit tests written for all new domain methods

## Testing

- **Existing tests to run**: `uv run pytest` — all 856 tests pass
- **New tests to write**: `TestTicketMoveToDoneWithPlan`, `TestTicketReopen`, `TestSprintTicketCounts`, `TestSprintArchive`
- **Verification command**: `uv run pytest`
