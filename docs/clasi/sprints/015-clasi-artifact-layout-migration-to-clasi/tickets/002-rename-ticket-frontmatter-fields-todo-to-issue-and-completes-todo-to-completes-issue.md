---
id: '002'
title: Rename ticket frontmatter fields `todo:` to `issue:` and `completes_todo:`
  to `completes_issue:`
status: done
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename ticket frontmatter fields `todo:` to `issue:` and `completes_todo:` to `completes_issue:`

## Description

Ticket frontmatter currently uses `todo:` to reference an issue file and `completes_todo:`
to control whether the linked issue is archived when the ticket completes. Both fields
must be renamed to use "issue" terminology.

Depends on ticket 001 because the template file is being edited in both tickets and the
status value must be correct before touching other template fields.

## Acceptance Criteria

- [x] `clasi/templates/ticket.md`: `todo: ""` field renamed to `issue: ""`
- [x] `clasi/templates/ticket.md`: `completes_todo:` renamed to `completes_issue:` (with updated comment)
- [x] `clasi/ticket.py`: `todo_ref` property renamed to `issue_ref`; reads `issue:` frontmatter key
- [x] `clasi/ticket.py`: `completes_todo_for(filename)` renamed to `completes_issue_for(filename)`
- [x] `clasi/tools/artifact_tools.py`: all reads of `todo:` / `completes_todo:` frontmatter keys updated
- [x] `clasi/sprint.py`: `create_ticket` template population updated
- [x] Full test suite passes

## Implementation Plan

### Approach
Update the template first, then update the code that reads/writes those fields.

### Files to modify
- `clasi/templates/ticket.md`
- `clasi/ticket.py`
- `clasi/tools/artifact_tools.py`
- `clasi/sprint.py`

### Testing plan
- `uv run pytest tests/unit/test_ticket.py` — verify field reads
- `uv run pytest` — full suite

### Documentation updates
None at this step; agent prompt updates are in ticket 024.
