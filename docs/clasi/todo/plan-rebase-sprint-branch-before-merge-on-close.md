---
status: pending
---

# Plan: Rebase sprint branch before merge on close

## Context

When closing a sprint, `close_sprint` merges the sprint branch into
master with `--no-ff`. This creates a merge commit (good) but the
sprint's commits may not sit cleanly on top of master if master
advanced during planning. Adding a rebase before the merge gives
clean linear history inside each sprint "bubble" in the git graph.

CLASI's execution lock prevents concurrent sprints, so master rarely
diverges during execution — but it can during planning (e.g., OOP
fixes, version bumps). Rebase-then-merge-no-ff is safe because sprint
branches are short-lived, single-user, and deleted after close.

## File to modify

`clasi/sprint.py` — `merge_branch()` method (line 263)

### Current flow (lines 301-312):
```python
checkout = subprocess.run(
    ["git", "checkout", main_branch], ...
)
merge = subprocess.run(
    ["git", "merge", "--no-ff", branch_name], ...
)
```

### New flow:
```python
# Rebase sprint branch onto main before merging
rebase = subprocess.run(
    ["git", "rebase", main_branch, branch_name],
    capture_output=True, text=True,
)
if rebase.returncode != 0:
    subprocess.run(["git", "rebase", "--abort"], capture_output=True)
    raise RuntimeError(
        f"Rebase of {branch_name} onto {main_branch} failed: "
        f"{rebase.stderr.strip()}"
    )

# Now checkout main and merge with --no-ff (unchanged)
checkout = subprocess.run(
    ["git", "checkout", main_branch], ...
)
merge = subprocess.run(
    ["git", "merge", "--no-ff", branch_name], ...
)
```

The rebase runs while still on whatever branch we're on (it checks
out `branch_name` internally). After rebase, the sprint commits sit
on top of `main_branch`. The `--no-ff` merge then creates the merge
commit wrapping the sprint.

### Update merge_strategy in artifact_tools.py

`clasi/tools/artifact_tools.py` line 1131 — change the reported
strategy from `"--no-ff"` to `"rebase + --no-ff"`.

### Update tests

`tests/unit/test_sprint.py` — existing `merge_branch` tests should
be updated or extended to verify the rebase step runs. Add a test
where master has advanced (a commit after the branch point) and
verify the sprint commits are replayed on top.

## Verification

1. Create a test branch, add a commit on master after branching,
   then close — verify `git log --oneline --graph` shows linear
   commits inside the merge bubble
2. `uv run pytest` passes
