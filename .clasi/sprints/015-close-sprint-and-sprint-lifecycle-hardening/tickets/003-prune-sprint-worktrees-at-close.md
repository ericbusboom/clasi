---
id: '003'
title: Prune sprint worktrees at close
status: in-progress
use-cases:
- SUC-015-002
depends-on:
- 015-002
github-issue: gh-14-cleanup-work-trees-after-sprint.md
issue: gh-14-cleanup-work-trees-after-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Prune sprint worktrees at close

## Description

Sprint execution creates one git worktree per ticket (via `acquire_execution_lock`). These
worktrees are never removed after the sprint closes, accumulating stale checkouts and
wasting disk space. Add a cleanup step to `_close_sprint_full` that prunes all git worktrees
associated with the closing sprint immediately after branch deletion.

## Acceptance Criteria

- [ ] A private `_prune_sprint_worktrees(sprint_id: str, branch_name: str) -> list[str]` helper
  is added to `clasi/tools/artifact_tools.py`.
- [ ] The helper parses `git worktree list --porcelain` and identifies worktrees whose `branch`
  field matches `refs/heads/<branch_name>` (where `branch_name` is the sprint branch, e.g.,
  `sprint/015-close-sprint-and-sprint-lifecycle-hardening`).
- [ ] Each matching worktree is removed via `git worktree remove --force <path>`.
- [ ] The helper is called as the final step of `_close_sprint_full`, after `delete_branch`.
- [ ] The result JSON includes `worktrees_pruned: [...]` (list of paths, empty if none found).
- [ ] A single failed worktree removal does not abort the close — failure is appended to
  `repairs` and the path is included in a `worktrees_failed` list in the result JSON.
- [ ] `close_sprint` succeeds and returns `status: closed` when no worktrees exist.
- [ ] `uv run pytest -q` passes with no regressions.

## Implementation Plan

### Approach

Parse `git worktree list --porcelain` output. The format is:
```
worktree /path/to/worktree
HEAD <sha>
branch refs/heads/sprint/NNN-slug

worktree /path/to/another
...
```

Build a list of `(path, branch)` tuples. Filter by `branch == f"refs/heads/{branch_name}"`.
For each match, call `subprocess.run(["git", "worktree", "remove", "--force", path])` and
collect results.

### Files to modify

1. **`clasi/tools/artifact_tools.py`**:
   - Add `_prune_sprint_worktrees(branch_name: str) -> tuple[list[str], list[str]]` helper
     returning `(pruned_paths, failed_paths)`.
   - In `_close_sprint_full`, after the `delete_branch` step completes, call
     `_prune_sprint_worktrees(branch_name)` and collect results.
   - Append to `completed_steps` only if at least one worktree was pruned.
   - Include `worktrees_pruned` and (if non-empty) `worktrees_failed` in the success result JSON.
   - Errors from individual removals go to `repairs` as well as `worktrees_failed`.

2. **Result JSON shape** (success path, new fields):
   ```json
   {
     "status": "closed",
     "sprint_id": "015",
     "worktrees_pruned": ["/path/to/worktree"],
     "worktrees_failed": [],
     "completed_steps": [..., "prune_worktrees"],
     ...
   }
   ```

### Testing plan

New test class `TestPruneSprintWorktrees` in `tests/unit/test_close_sprint_worktrees.py` (new file):

- **`test_prune_worktrees_no_worktrees`**: Mock `git worktree list --porcelain` to return only
  the main worktree (no sprint branches). Assert `worktrees_pruned: []` and no subprocess calls
  for removal.
- **`test_prune_worktrees_matching_branch`**: Mock `git worktree list --porcelain` to return one
  worktree with the sprint branch. Assert `git worktree remove --force <path>` is called and the
  path appears in `worktrees_pruned`.
- **`test_prune_worktrees_non_blocking_failure`**: Mock removal to return non-zero exit code.
  Assert `close_sprint` still returns `status: closed` and the failed path appears in
  `worktrees_failed`.
- **`test_prune_worktrees_multiple`**: Two matching worktrees; both pruned; result lists both paths.

Integration point: the `close_sprint` integration tests in `test_sweep_done_issues.py` mock
`subprocess.run` — ensure those mocks do not inadvertently intercept the new worktree calls
(scope mocks to specific commands if needed).

### Documentation updates

Update `clasi/plugin/skills/close-sprint/SKILL.md`: add a brief note under the existing flow
description that `close_sprint` prunes sprint worktrees as the final step, and the result JSON
includes a `worktrees_pruned` list.
