---
id: '003'
title: Sprint-scoped log directories
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: sprint-scoped-log-directories.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint-scoped log directories

## Description

Hook handlers (SubagentStart, SubagentStop, TaskCreated, TaskCompleted) write logs
to a sprint-scoped subdirectory (`docs/clasi/log/sprint-{sprint_id}/`) when an
execution lock is held, and fall back to `docs/clasi/log/` otherwise.

## Acceptance Criteria

- [x] `_get_log_dir()` helper in `clasi/hook_handlers.py` reads the execution lock from the state DB
- [x] When a sprint holds the lock, logs go to `docs/clasi/log/sprint-{sprint_id}/`
- [x] The `.active/` marker directory is also scoped to the sprint subdirectory
- [x] When no lock exists, logs fall back to `docs/clasi/log/`
- [x] When no state DB exists, logs fall back to `docs/clasi/log/`
- [x] All four handlers use `_get_log_dir()` instead of hardcoded `Path("docs/clasi/log")`

## Testing

- **Existing tests to run**: `tests/unit/test_hook_handlers.py`
- **New tests to write**: `TestGetLogDir` and `TestSprintScopedLogging` classes — 9 new tests
- **Verification command**: `uv run pytest --no-cov`
