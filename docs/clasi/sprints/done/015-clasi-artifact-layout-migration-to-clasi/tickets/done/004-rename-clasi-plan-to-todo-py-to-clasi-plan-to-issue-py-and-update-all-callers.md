---
id: '004'
title: Rename `clasi/plan_to_todo.py` to `clasi/plan_to_issue.py` and update all callers
status: done
use-cases:
- SUC-001
depends-on:
- '003'
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename `clasi/plan_to_todo.py` to `clasi/plan_to_issue.py` and update all callers

## Description

Rename `clasi/plan_to_todo.py` to `clasi/plan_to_issue.py`. Inside the file, rename the
functions `plan_to_todo` → `plan_to_issue` and `plan_to_todo_from_text` → `plan_to_issue_from_text`.
Update all callers in `clasi/cli.py` and `clasi/hook_handlers.py`.

## Acceptance Criteria

- [x] `clasi/plan_to_issue.py` exists; `clasi/plan_to_todo.py` is deleted
- [x] Functions renamed: `plan_to_issue`, `plan_to_issue_from_text`
- [x] `clasi/cli.py` imports from `plan_to_issue` and calls renamed functions
- [x] `clasi/hook_handlers.py` imports from `plan_to_issue` and calls renamed functions
- [x] `tests/unit/test_plan_to_todo.py` renamed to `tests/unit/test_plan_to_issue.py`
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/plan_to_todo.py` (rename to `clasi/plan_to_issue.py`)
- `clasi/cli.py` — import and call sites
- `clasi/hook_handlers.py` — import and call sites
- `tests/unit/test_plan_to_todo.py` (rename)

### Testing plan
- `uv run pytest tests/unit/test_plan_to_issue.py`
- `uv run pytest` — full suite
