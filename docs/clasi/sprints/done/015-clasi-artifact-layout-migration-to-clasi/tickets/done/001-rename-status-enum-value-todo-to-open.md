---
id: '001'
title: Rename status enum value `todo` to `open`
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename status enum value `todo` to `open`

## Description

Tickets that have not yet started are currently given `status: todo`. This collides
with the artifact concept being renamed (the "TODO" / "issue" file). Rename the status
value to `open` to match GitHub/Jira terminology and avoid the naming collision.

This is the foundation for all subsequent rename work — other tickets depend on the
template and validators being updated first.

## Acceptance Criteria

- [x] `clasi/templates/ticket.md`: `status: todo` default changed to `status: open`
- [x] `clasi/templates.py` (if it defines status constants or defaults): `"todo"` → `"open"` (no status constants defined; file only loads templates)
- [x] `clasi/state_db.py` or `clasi/state_db_class.py`: any status checks for `"todo"` updated (no ticket status references in these files)
- [x] `clasi/contracts.py` or validation: status enum updated to include `"open"`, remove `"todo"` (no ticket status enum in contracts.py; valid_statuses set updated in artifact_tools.py)
- [x] `clasi/hook_handlers.py`: any `status == "todo"` checks updated to `status == "open"` (no ticket status checks in hook_handlers.py)
- [x] `clasi/ticket.py`: any status checks or constants updated (default fallback and reopen() method)
- [x] `clasi/tools/artifact_tools.py`: status references updated (valid_statuses, docstrings, pre-execution check)
- [x] `clasi/sprint.py`: any status references updated (ticket_counts() key renamed todo→open)
- [x] All existing tickets in active sprints are NOT mutated (historical data)
- [x] Full test suite passes (1290 passed, 85.87% coverage)

## Implementation Plan

### Approach
Search for all occurrences of `"todo"` as a status value (distinct from the word "todo"
in comments or issue filenames) using: `grep -rn 'status.*todo\|todo.*status\|"todo"' clasi/ tests/`

### Files to modify
- `clasi/templates/ticket.md` — default status line
- `clasi/templates.py` — any `TICKET_STATUS_TODO` constant or similar
- `clasi/contracts.py` — ticket status enum / validator
- `clasi/state_db.py` or `clasi/state_db_class.py` — status queries
- `clasi/hook_handlers.py` — status checks
- `clasi/ticket.py` — status property, `is_todo()` or similar predicates
- `clasi/tools/artifact_tools.py` — tool logic referencing status

### Testing plan
- Run `uv run pytest tests/unit/test_ticket.py tests/unit/test_sprint.py` to confirm
  status validation passes with the new value.
- Run `uv run pytest` for full suite.

### Documentation updates
None — this is an internal enum change; agent prompts are updated in ticket 024.
