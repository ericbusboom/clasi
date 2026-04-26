---
id: '001'
title: Fix close_sprint dirty-tree failure and lock leak
status: todo
use-cases:
  - SUC-001
  - SUC-002
depends-on: []
github-issue: ''
todo: close-sprint-rebase-fails-on-dirty-clasi-db.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix close_sprint dirty-tree failure and lock leak

## Description

`close_sprint` fails every time it is called on a project where `docs/clasi/.clasi.db`
is git-tracked. The lifecycle writes to `.clasi.db` in step 4 (`db_update`), but the
rebase in step 6 (`merge`) requires a clean working tree. Additionally, when merge fails
for any reason the execution lock is left held, forcing a manual `release_execution_lock`
call before the agent can retry.

This ticket fixes both issues in `clasi/tools/artifact_tools.py` in
`_close_sprint_full`:

1. After `version_bump` (step 5), check whether `docs/clasi/.clasi.db` is still dirty
   (i.e., versioning was skipped or `git add -A` didn't commit it). If so, stage and
   commit it on the sprint branch with message `"chore: update .clasi.db"` before
   proceeding to the rebase.
2. Wrap the merge step (step 6) in a try/finally so that `db.release_lock(sprint_id)`
   is called even when merge raises `RuntimeError` or `MergeConflictError`.

## Acceptance Criteria

- [ ] `close_sprint` completes without "You have unstaged changes" error when
      `docs/clasi/.clasi.db` is git-tracked and dirty after `db_update`.
- [ ] After a simulated merge failure the execution lock is not held (verified by
      inspecting DB state in tests).
- [ ] The `.clasi.db` commit guard only runs if the file appears as `modified` in
      `git status --porcelain`; it is a no-op when the file is gitignored or clean.
- [ ] The guard asserts that `HEAD` is the sprint branch before committing (guards
      against accidental commits on main).
- [ ] All existing `close_sprint` tests continue to pass.
- [ ] New tests cover: (a) dirty `.clasi.db` scenario with versioning disabled, (b)
      dirty `.clasi.db` scenario with versioning enabled, (c) lock release after
      simulated merge failure.

## Implementation Plan

### Approach

Modify `_close_sprint_full` in `clasi/tools/artifact_tools.py`:

**Step 5 extension (after the existing version_bump block)**:
```python
# Guard: commit .clasi.db if still dirty after version_bump
db_file = project.root / "docs" / "clasi" / ".clasi.db"
if db_file.exists():
    status = subprocess.run(
        ["git", "status", "--porcelain", str(db_file)],
        capture_output=True, text=True, cwd=str(project.root)
    )
    if status.stdout.strip():  # non-empty means dirty/staged
        # Verify we're on the sprint branch before committing
        head_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(project.root)
        ).stdout.strip()
        if head_branch == sprint.branch:
            subprocess.run(
                ["git", "add", str(db_file)],
                cwd=str(project.root), capture_output=True, text=True
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: update .clasi.db"],
                cwd=str(project.root), capture_output=True, text=True
            )
```

**Step 6 lock-release finally**:
```python
try:
    merge_result = archived_sprint.merge_branch(main_branch)
    ...
except RuntimeError as e:
    ...
    return json.dumps({...})  # existing error return
finally:
    # Release lock regardless of merge outcome
    if db.path.exists():
        try:
            db.release_lock(sprint_id)
        except ValueError:
            pass  # already released (success path)
```

Note: the existing success path releases the lock in `db_update` (step 4). The finally
block is idempotent — `release_lock` raises `ValueError` if not held, which is caught.

### Files to Modify

- `clasi/tools/artifact_tools.py` — `_close_sprint_full` function, steps 5 and 6.

### Files to Create or Modify (Tests)

- `tests/unit/test_close_sprint.py` (create if not exists, or extend existing):
  - Test: `db_update` dirtying `.clasi.db` → guard commits → rebase succeeds.
  - Test: versioning active → `git add -A` cleans tree → guard is no-op.
  - Test: merge raises `RuntimeError` → lock is released in finally.
  - Use `unittest.mock.patch` for `subprocess.run` and `db.release_lock`.

### Testing Plan

1. Run `uv run pytest tests/unit/test_close_sprint.py -v` for new tests.
2. Run `uv run pytest` for full suite regression check.

### Documentation Updates

None required (the fix is behavioral, not interface-changing). The TODO file
`close-sprint-rebase-fails-on-dirty-clasi-db.md` is moved to done when this ticket
is complete.
