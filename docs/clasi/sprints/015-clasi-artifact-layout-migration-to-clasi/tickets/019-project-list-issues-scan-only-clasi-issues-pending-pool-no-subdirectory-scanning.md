---
id: 019
title: '`Project.list_issues()`: scan only `.clasi/issues/` pending pool (no subdirectory
  scanning)'
status: open
use-cases:
  - SUC-002
depends-on:
  - "018"
github-issue: ''
todo: sprint-scoped-issues-directory.md
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `Project.list_issues()`: scan only `.clasi/issues/` pending pool (no subdirectory scanning)

## Description

Update `Project.list_issues()` (formerly `list_todos()`) to scan only
`.clasi/issues/*.md` — the pending pool. It must NOT scan `in-progress/` or `done/`
subdirs (they no longer exist). Sprint-specific in-progress issues are retrieved via
`Sprint.list_issues()`, not `Project.list_issues()`.

Also update `Project.get_issue(filename)` to search: first `.clasi/issues/<filename>`,
then every sprint's `<sprint>/issues/<filename>` (active sprints). Remove searches for
`in-progress/` and `done/` subdirs.

## Acceptance Criteria

- [ ] `Project.list_issues()` returns only pending pool issues (`.clasi/issues/*.md`)
- [ ] `Project.get_issue(filename)` finds pending issues and sprint-scoped issues
- [ ] No scan of `in-progress/` or `done/` subdirectory (those don't exist)
- [ ] Tests verify: pending issue is found; sprint-scoped issue is found via sprint
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/project.py` — `list_issues`, `get_issue` methods
- `clasi/tools/artifact_tools.py` — `list_issues` MCP tool if it has its own scan logic

### Testing plan
- `uv run pytest tests/unit/test_project.py`
- `uv run pytest` — full suite
