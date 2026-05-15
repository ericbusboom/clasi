---
id: '001'
title: Rename production-code identifiers from todo to issue
status: done
use-cases:
- SUC-001
depends-on: []
issue: finish-the-todo-issue-rename.md
---

## Description

Rename all `todo`-named Python parameters, local variables, and private helper
functions in production code. No behavioral change — purely mechanical
identifier renames with caller updates.

Files in scope:
- `clasi/plan_to_issue.py` — parameter rename
- `clasi/sprint.py` — parameter and local variable rename
- `clasi/tools/artifact_tools.py` — parameter, locals, private helpers, and JSON output keys
- `clasi/cli.py` — caller update (kwarg rename)
- `clasi/hook_handlers.py` — caller update (kwarg rename)

## Acceptance Criteria

- [x] `plan_to_issue(plans_dir, todo_dir, ...)` parameter renamed to `issue_dir` in both `plan_to_issue` and `plan_to_issue_from_text`
- [x] `todo_dir.mkdir()` call inside both functions updated to `issue_dir.mkdir()`
- [x] Callers in `cli.py` and `hook_handlers.py` pass `issue_dir=...` (not `todo_dir=...`)
- [x] `Sprint.create_ticket(title, todo=...)` parameter renamed to `issue`; local `sprint_todos` → `sprint_issues`
- [x] `artifact_tools.create_ticket` MCP-tool wrapper: `todo` parameter → `issue`; local variables `completed_todos` → `completed_issues`, `moved_todos` → `moved_issues`, `unresolved_todos` → `unresolved_issues`
- [x] Private helpers `_any_ticket_suppresses_todo` → `_any_ticket_suppresses_issue` and `_todo_is_deferred` → `_issue_is_deferred` in `artifact_tools.py`
- [x] `close_sprint` result JSON keys `moved_todos` → `moved_issues` and `unresolved_todos` → `unresolved_issues`
- [x] All internal call sites updated (references to `sprint_todos`, `todo_arg`, `todo_list`, `todo_obj`, `todo_filename` local variables renamed consistently)
- [x] `grep -n "todo" clasi/plan_to_issue.py clasi/sprint.py clasi/tools/artifact_tools.py` returns no hits outside the out-of-scope list
- [x] Full test suite passes

## Implementation Plan

### Approach

Pure search-and-replace at identifier boundaries. Work file by file. After
each file, run the test suite to catch any missed caller update early.

### Files to Modify

- `clasi/plan_to_issue.py` — rename `todo_dir` parameter in two function
  signatures and the body references
- `clasi/sprint.py` — rename `todo` parameter to `issue` in `create_ticket`;
  rename `sprint_todos` to `sprint_issues` in the body
- `clasi/tools/artifact_tools.py` — rename `todo` parameter in `create_ticket`
  wrapper; rename `completed_todos`, `moved_todos`, `unresolved_todos` locals;
  rename `_any_ticket_suppresses_todo` → `_any_ticket_suppresses_issue` and
  `_todo_is_deferred` → `_issue_is_deferred` and all their call sites; rename
  JSON output keys in `close_sprint`
- `clasi/cli.py` — update kwarg at call site of `plan_to_issue`
- `clasi/hook_handlers.py` — update kwarg at call site of `plan_to_issue` /
  `plan_to_issue_from_text` (only the call-site kwarg; do not touch the
  backward-compat alias functions or registry keys)

### Testing Plan

- Run `pytest tests/unit/` after each file. A broken kwarg rename shows up
  immediately as a TypeError.
- After all files: run full suite and confirm green.
- Run `grep -n "\btodo\b" clasi/plan_to_issue.py clasi/sprint.py clasi/tools/artifact_tools.py clasi/cli.py clasi/hook_handlers.py` and verify every remaining hit is on the out-of-scope list.

### Documentation Updates

None for this ticket. Docstring prose is handled in ticket 002.
