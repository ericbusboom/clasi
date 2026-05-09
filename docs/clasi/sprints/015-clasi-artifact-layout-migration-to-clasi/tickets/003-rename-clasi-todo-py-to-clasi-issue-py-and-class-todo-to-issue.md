---
id: '003'
title: Rename `clasi/todo.py` to `clasi/issue.py` and class `Todo` to `Issue`
status: done
use-cases:
  - SUC-001
depends-on:
  - "002"
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename `clasi/todo.py` to `clasi/issue.py` and class `Todo` to `Issue`

## Description

Create `clasi/issue.py` as the renamed version of `clasi/todo.py`. The class `Todo`
becomes `Issue`. All internal imports across the codebase are updated. `clasi/todo.py`
is removed. Lifecycle method signatures stay the same; behavioral changes come in
tickets 016-019.

## Acceptance Criteria

- [x] `clasi/issue.py` exists with class `Issue` (was `Todo`)
- [x] `clasi/todo.py` is deleted
- [x] All imports updated: `from clasi.todo import Todo` becomes `from clasi.issue import Issue`
- [x] Callers in `clasi/project.py`, `clasi/sprint.py`, `clasi/hook_handlers.py`,
  `clasi/tools/artifact_tools.py`, `clasi/cli.py`, `clasi/init_command.py` updated
- [x] `tests/unit/test_todo.py` renamed to `tests/unit/test_issue.py` with class/import updates
- [x] Full test suite passes

## Implementation Plan

### Approach
1. Copy `clasi/todo.py` to `clasi/issue.py`.
2. Rename class `Todo` to `Issue` inside the new file.
3. Update all import sites.
4. Delete `clasi/todo.py`.
5. Rename test file.

### Files to modify
- `clasi/todo.py` (delete after copying)
- `clasi/issue.py` (create)
- `clasi/project.py`, `clasi/sprint.py`, `clasi/hook_handlers.py`,
  `clasi/tools/artifact_tools.py`, `clasi/cli.py`, `clasi/init_command.py`
- `tests/unit/test_todo.py` (rename to `test_issue.py`)

### Testing plan
- `uv run pytest tests/unit/test_issue.py` — all existing todo tests pass with new class name
- `uv run pytest` — full suite

### Documentation updates
None at this step.
