---
id: '005'
title: Rename test class and method names from todo to issue
status: done
use-cases:
- SUC-005
depends-on:
- '001'
issue: finish-the-todo-issue-rename.md
---

## Description

Rename test class names, method names, and local variable names that use the
old `todo` vocabulary. Also update any test assertions that check for the
`moved_todos` / `unresolved_todos` JSON keys (renamed in ticket 001).

Files in scope (from the issue audit):
- `tests/unit/test_hook_handlers.py`
- `tests/unit/test_issue_tools.py`
- `tests/unit/test_plan_to_issue.py`
- `tests/unit/test_issue_lifecycle.py`

## Acceptance Criteria

- [x] `test_hook_handlers.py`: `TestHandlePlanToTodo` → `TestHandlePlanToIssue`
- [x] `test_hook_handlers.py`: `TestHandleCodexPlanToTodo` → `TestHandleCodexPlanToIssue`
- [x] `test_hook_handlers.py`: `TestHandleHookCodexPlanToTodo` → `TestHandleHookCodexPlanToIssue`
- [x] `test_hook_handlers.py`: method names containing `_todo_` or `_todo` updated to use `_issue_` / `_issue` (e.g., `test_calls_plan_to_todo_with_standard_dirs` → `test_calls_plan_to_issue_with_standard_dirs`)
- [x] `test_issue_tools.py:285`: `test_todo_moves_to_in_progress_not_done` → `test_issue_moves_to_in_progress_not_done`
- [x] `test_issue_tools.py`: `TestCreateTicketWithTodo` class renamed to `TestCreateTicketWithIssue`; method names `test_creates_ticket_with_todo_field`, `test_updates_todo_frontmatter_on_create`, `test_multiple_todos`, `test_multiple_tickets_same_todo` renamed accordingly; any local variable named `todo_dir` renamed to `issue_dir`; fixture `todo_dir` renamed to `issue_dir`
- [x] `test_plan_to_issue.py`: full audit — all class/method names containing `todo` renamed; no logic changes
- [x] `test_issue_lifecycle.py`: all method names containing `_todo_` or `_todo` renamed (e.g., `test_moves_todo_from_pending_to_in_progress` → `test_moves_issue_from_pending_to_in_progress`)
- [x] Any test asserting on `"moved_todos"` or `"unresolved_todos"` JSON keys updated to `"moved_issues"` / `"unresolved_issues"` (consistent with ticket 001)
- [x] Full test suite passes after all renames

## Implementation Plan

### Approach

Work file by file. For each file, audit all class names, method names,
fixture names, and local variable names. Rename `todo` → `issue` consistently.
After renaming, run `pytest <file>` to confirm the file is green before
moving to the next.

Special care for `test_issue_tools.py` fixture `todo_dir`: if it is a
`pytest.fixture` name, all references to it in the same file must be renamed
in the same pass.

For JSON key assertions: search each test file for `"moved_todos"` and
`"unresolved_todos"` string literals and update them. These correspond to
the renames made in ticket 001.

### Files to Modify

- `tests/unit/test_hook_handlers.py`
- `tests/unit/test_issue_tools.py`
- `tests/unit/test_plan_to_issue.py`
- `tests/unit/test_issue_lifecycle.py`

### Testing Plan

- Run `pytest tests/unit/<file>` after each file to catch any reference
  missed in the rename.
- Final: run full `pytest tests/` to confirm suite is green.
- Run `grep -n "\btodo\b" tests/unit/test_hook_handlers.py tests/unit/test_issue_tools.py tests/unit/test_plan_to_issue.py tests/unit/test_issue_lifecycle.py` and confirm every remaining hit is a string literal being tested (not a test identifier).

### Documentation Updates

None. This ticket is purely test cleanup.

### Note on depends-on

This ticket depends on ticket 001 because it must update JSON key assertions
for `moved_issues` / `unresolved_issues`. It can run in parallel with tickets
002, 003, 004 from a code perspective, but is ordered after 001 for clarity
and to avoid split-diff confusion.
