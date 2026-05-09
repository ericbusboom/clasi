---
id: '005'
title: 'Update `Project` methods: `get_todo` to `get_issue`, `list_todos` to `list_issues`,
  `todo_dir` to `issues_dir`'
status: open
use-cases:
  - SUC-001
  - SUC-002
depends-on:
  - "003"
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update `Project` methods: `get_todo` to `get_issue`, `list_todos` to `list_issues`, `todo_dir` to `issues_dir`

## Description

Rename the `Project` class methods and properties that reference the old "todo" name.
The internal path returned by `issues_dir` still points to `self.clasi_dir / "issues"` —
the actual path value changes in ticket 006 when `clasi_dir` is updated.

## Acceptance Criteria

- [ ] `Project.todo_dir` property renamed to `Project.issues_dir`
- [ ] `Project.get_todo(filename)` renamed to `Project.get_issue(filename)`
- [ ] `Project.list_todos()` renamed to `Project.list_issues()`
- [ ] All callers of these methods updated across the codebase
  (`hook_handlers.py`, `artifact_tools.py`, `sprint.py`, `cli.py`, `init_command.py`)
- [ ] TYPE_CHECKING imports updated to use `Issue` not `Todo`
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/project.py` — method/property renames
- `clasi/hook_handlers.py`, `clasi/tools/artifact_tools.py`, `clasi/sprint.py`,
  `clasi/cli.py`, `clasi/init_command.py` — call sites

### Testing plan
- `uv run pytest tests/unit/test_project.py`
- `uv run pytest` — full suite
