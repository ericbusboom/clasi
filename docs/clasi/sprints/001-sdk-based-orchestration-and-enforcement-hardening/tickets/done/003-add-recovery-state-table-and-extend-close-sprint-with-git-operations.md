---
id: '003'
title: Add recovery_state table and extend close_sprint with git operations
status: in-progress
use-cases:
- SUC-003
- SUC-004
depends-on:
- '002'
github-issue: ''
todo: sdk-orchestration-cluster/absorb-git-close-into-close-sprint.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add recovery_state table and extend close_sprint with git operations

## Description

Extend the `close_sprint` MCP tool from a simple archive operation into
a comprehensive sprint closure command that handles git operations,
precondition verification with self-repair, and failure recovery. This
eliminates the 15-step manual close-sprint skill and replaces it with a
3-step process: confirm readiness, call `close_sprint`, report results.

### Recovery State Table

Add a `recovery_state` table to `state_db.py` that tracks failure state
when `close_sprint` encounters an unrecoverable error mid-execution.
This table stores the sprint ID, the step that failed, the list of file
paths the agent is allowed to edit to fix the issue, and a timestamp.

Functions to add:
- `write_recovery_state(sprint_id, step, allowed_paths, reason)` --
  Records a failure for later recovery.
- `get_recovery_state(sprint_id)` -- Retrieves the current recovery
  record, if any.
- `clear_recovery_state(sprint_id)` -- Clears the record after
  successful recovery.
- TTL mechanism: records older than 24 hours are automatically cleared
  on read.

### Extended close_sprint

Accept new parameters: `branch_name`, `main_branch`, `push_tags`,
`delete_branch`. When `branch_name` is omitted, fall back to current
behavior (backward compatible).

Execution sequence:
1. Pre-condition verification with self-repair (tickets in done/,
   TODOs resolved, state DB in sync, execution lock held).
2. Run `uv run pytest` to verify tests pass.
3. Archive sprint directory to `sprints/done/`.
4. Update state DB phase to `done`.
5. Bump version and create git tag.
6. `git checkout <main_branch> && git merge --no-ff <branch_name>`.
7. `git push --tags` (if `push_tags` is true).
8. `git branch -d <branch_name>` (if `delete_branch` is true).
9. Release execution lock.

Each step must be idempotent -- if `close_sprint` is called again after
a failure, it detects which steps already completed and skips them.

On failure, write a `recovery_state` record with the failed step and
allowed paths, then return a structured error JSON.

### close-sprint Skill Update

Update the close-sprint skill definition from its current 15 manual
steps to 3 steps: confirm, call close_sprint, report.

## Acceptance Criteria

- [ ] `recovery_state` table exists in `state_db.py` schema
- [ ] `write_recovery_state`, `get_recovery_state`, `clear_recovery_state` functions exist
- [ ] TTL: stale records (>24h) are auto-cleared on read
- [ ] `close_sprint` accepts `branch_name`, `main_branch`, `push_tags`, `delete_branch` parameters
- [ ] Backward compatible: omitting `branch_name` falls back to current behavior
- [ ] Pre-condition verification with self-repair (tickets, TODOs, state DB, execution lock)
- [ ] Git operations: test run, merge --no-ff, push tags, branch delete
- [ ] Structured result JSON on success with per-step outcomes
- [ ] Structured error JSON with recovery state on failure
- [ ] Each step is idempotent (detects already-completed steps on retry)
- [ ] close-sprint skill updated to 3 steps
- [ ] Unit tests with mocked subprocess for git operations
- [ ] Unit tests for recovery state CRUD and TTL

## Testing

- **Existing tests to run**: `tests/test_artifact_tools.py` (close_sprint backward compat), `tests/test_state_db.py`
- **New tests to write**: New tests in `tests/test_state_db.py` for recovery_state CRUD and TTL; new tests in `tests/test_artifact_tools.py` for extended close_sprint with mocked subprocess (merge success, merge conflict, test failure, idempotent retry)
- **Verification command**: `uv run pytest`
