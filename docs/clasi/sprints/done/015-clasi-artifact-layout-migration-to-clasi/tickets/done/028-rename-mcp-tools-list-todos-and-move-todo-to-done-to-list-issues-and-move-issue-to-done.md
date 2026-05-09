---
id: 028
title: Rename MCP tools list_todos and move_todo_to_done to list_issues and move_issue_to_done
status: done
use-cases:
- SUC-001
depends-on:
- 019
- '027'
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename MCP tools list_todos and move_todo_to_done to list_issues and move_issue_to_done

## Description

Rename the two MCP tool functions in `clasi/tools/artifact_tools.py`:
- `list_todos()` → `list_issues()`
- `move_todo_to_done()` → `move_issue_to_done()`

This is the LAST ticket because the running MCP server still exposes the old tool names
throughout sprint execution. Renaming mid-sprint would break any agent session that is
actively calling `list_todos` or `move_todo_to_done`. The server restarts at sprint
close, at which point the new names become the live API.

After this ticket, the `rename-clasi-todos-to-issues.md` issue is fully resolved.

## Acceptance Criteria

- [x] `list_todos` decorated function renamed to `list_issues` in `artifact_tools.py`
- [x] `move_todo_to_done` decorated function renamed to `move_issue_to_done`
- [x] All internal references within `artifact_tools.py` updated
- [x] Docstrings updated to use "issue" language
- [x] MCP server schema updated: new tool names exposed, old names gone
- [x] `tests/unit/test_todo_tools.py` (now `test_issue_tools.py` from ticket 027)
  passes with new function names
- [x] `uv run pytest` — full suite green

## Implementation Plan

### Files to modify
- `clasi/tools/artifact_tools.py` — function rename + decorator name update

### Testing plan
- `uv run pytest tests/unit/test_issue_tools.py`
- `uv run pytest` — full suite

### Important ordering note
This ticket MUST be last. Do not execute until all other 27 tickets are done.
The MCP server restart at `close_sprint` activates the new tool names for downstream
sessions.
