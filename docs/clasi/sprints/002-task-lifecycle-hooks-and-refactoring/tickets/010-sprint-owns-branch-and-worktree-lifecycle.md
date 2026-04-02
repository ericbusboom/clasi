---
id: '010'
title: Sprint owns branch and worktree lifecycle
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: sprint-owns-branch-and-worktree-lifecycle.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint owns branch and worktree lifecycle

## Description

The Sprint class in `clasi/sprint.py` now owns the logic for creating,
merging, and deleting a sprint git branch.  Previously this logic was
scattered inline in `clasi/tools/artifact_tools.py`.

## Acceptance Criteria

- [x] `Sprint.create_branch()` creates (or checks out) the sprint branch
- [x] `Sprint.merge_branch(main_branch)` merges the sprint branch into main, idempotently
- [x] `Sprint.delete_branch()` deletes the sprint branch (safe-delete only)
- [x] `MergeConflictError` carries the list of conflicted files
- [x] Callers in `artifact_tools.py` use the Sprint methods instead of inline git commands
- [x] All existing tests pass (`uv run pytest`)

## Testing

- **Existing tests run**: full suite — 827 passed, 0 failed
- **New tests written**: `TestSprintCreateBranch`, `TestSprintMergeBranch`,
  `TestSprintDeleteBranch` in `tests/unit/test_sprint.py` (24 new tests)
- **Verification command**: `uv run pytest`
