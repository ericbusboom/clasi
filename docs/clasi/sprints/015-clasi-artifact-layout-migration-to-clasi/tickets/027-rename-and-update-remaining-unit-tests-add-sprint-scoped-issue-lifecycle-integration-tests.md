---
id: "027"
title: "Rename and update remaining unit tests; add sprint-scoped issue lifecycle integration tests"
status: open
use-cases:
  - SUC-001
  - SUC-002
depends-on:
  - "016"
  - "017"
  - "018"
  - "019"
  - "025"
  - "026"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename and update remaining unit tests; add sprint-scoped issue lifecycle integration tests

## Description

Finish all test file updates not covered by tickets 025-026, and add new lifecycle tests:

**File renames:**
- `tests/unit/test_todo_lifecycle.py` → `tests/unit/test_issue_lifecycle.py`
- `tests/unit/test_todo_tools.py` → `tests/unit/test_issue_tools.py`
- (Already done in 003: `test_todo.py` → `test_issue.py`)
- (Already done in 004: `test_plan_to_todo.py` → `test_plan_to_issue.py`)

**File updates (remaining):**
- `tests/unit/test_dispatch_log.py` (14 occurrences)
- `tests/unit/test_init_command.py` — `.clasi/` layout
- `tests/unit/test_project.py` — path fixtures
- `tests/unit/test_sprint.py` — Sprint.issues_dir, list_issues, archive
- `tests/unit/test_state_db.py` — DB path
- `tests/unit/test_agent.py` — if it references old paths
- `tests/system/test_artifact_tools.py` (3 occurrences)

**New tests:**
- `tests/unit/test_issue_lifecycle.py`: install → create issue → `move_to_in_progress`
  with sprint → assert file at `<sprint>/issues/` → `move_to_done` → assert frontmatter
  → archive sprint → assert file at `done/<sprint>/issues/`
- `Sprint.issues_dir` and `Sprint.list_issues()` unit tests

## Acceptance Criteria

- [ ] All test files renamed as specified
- [ ] No `docs/clasi` string literals in any test file (done/ sprint archives exempt)
- [ ] No `status: todo` in fixtures (use `status: open`)
- [ ] Sprint-scoped issue lifecycle integration test passes end-to-end
- [ ] `grep -rn "docs/clasi" tests/` returns zero hits (excluding done-sprint archives)
- [ ] `uv run pytest` — full suite green

## Implementation Plan

### Files to modify/rename
- `tests/unit/test_todo_lifecycle.py`, `test_todo_tools.py` (rename)
- `tests/unit/test_dispatch_log.py`, `test_init_command.py`, `test_project.py`,
  `test_sprint.py`, `test_state_db.py`, `test_agent.py` (update)
- `tests/system/test_artifact_tools.py` (update)
- `tests/unit/test_issue_lifecycle.py` (new)

### Testing plan
- `uv run pytest` — must be fully green after this ticket
