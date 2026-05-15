---
id: '002'
title: 'Close-sprint precondition: done-dir awareness and legacy migration'
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Close-sprint precondition: done-dir awareness and legacy migration

## Description

Update `_close_sprint_full` and `_close_sprint_legacy` in `clasi/tools/artifact_tools.py` so that the precondition pass correctly handles three scenarios:

1. **Issues already in `issues/done/`** — pass cleanly, no action needed.
2. **Done-tagged issues still at `issues/` top-level** — self-repair by calling `todo.move_to_done()` (which now physically moves the file). The existing repair message "moved TODO ... to done/" becomes accurate.
3. **Pending-pool issues with `sprint == sprint_id` and `status: done`** — self-repair by manually relocating to `<sprint>/issues/done/` before calling `move_to_done` for frontmatter only.

Scenario 3 requires special handling: calling `todo.move_to_done()` directly on a pool-resident file would move it to `.clasi/issues/done/` (wrong location). The fix is an inline relocation step.

Depends on T1 (`Issue.move_to_done` file relocation).

## Acceptance Criteria

- [x] `_close_sprint_full` step 1b: issues in `<sprint>/issues/done/` are scanned and pass cleanly (no repair logged, no error).
- [x] `_close_sprint_full` step 1b: issues at `<sprint>/issues/` top level with `status: done` are moved to `<sprint>/issues/done/` by self-repair and the repair message is logged.
- [x] `_close_sprint_full` step 1b: pending-pool issues with `sprint == sprint_id` and `status: done` are relocated to `<sprint>/issues/done/` and logged as repairs.
- [x] `_close_sprint_full` step 1b: an issue at `<sprint>/issues/` top level with `status: in-progress` that is not deferred still hard-fails (no regression).
- [x] Same four behaviors hold for `_close_sprint_legacy`.
- [x] Existing close-sprint precondition tests pass without modification (or are updated if they were asserting pre-T1 behavior).
- [x] New close-sprint precondition tests pass covering the three scenarios.
- [x] `uv run pytest tests/unit/test_artifact_tools.py -x` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### _close_sprint_full — step 1b rewrite (around lines 971-1020)

Replace the current `in_progress_todo_dir` scan with a two-part scan:

**Part 1: scan `<sprint>/issues/` (top-level)**
```python
sprint_issues_dir = sprint.path / "issues"
if sprint_issues_dir.exists():
    for todo_file in sorted(sprint_issues_dir.glob("*.md")):
        todo = Issue(todo_file, project)
        if todo.sprint == sprint_id:
            if todo.status in ("done", "complete", "completed"):
                todo.move_to_done()  # now physically relocates
                repairs.append(f"moved TODO {todo_file.name} to done/")
            else:
                if _todo_is_deferred(sprint, todo_file.name):
                    continue
                # hard-fail (existing code unchanged)
                ...
```

**Part 2: scan `<sprint>/issues/done/` (already relocated)**
```python
sprint_issues_done_dir = sprint.path / "issues" / "done"
if sprint_issues_done_dir.exists():
    for todo_file in sorted(sprint_issues_done_dir.glob("*.md")):
        todo = Issue(todo_file, project)
        # Already in done/ — pass cleanly, no action needed
        pass
```

**Part 3: pending-pool scan — inline relocation fix**

Replace the existing pending-pool block (lines 1011-1020):
```python
pending_pool = project.issues_dir
if pending_pool.exists():
    for todo_file in sorted(pending_pool.glob("*.md")):
        todo = Issue(todo_file, project)
        if todo.sprint == sprint_id:
            if todo.status in ("done", "complete", "completed"):
                # Relocate directly to <sprint>/issues/done/ (not pool/done/)
                target_dir = sprint.path / "issues" / "done"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / todo_file.name
                todo_file.rename(target_path)
                from clasi.artifact import Artifact
                todo._artifact = Artifact(target_path)
                # Now call move_to_done for frontmatter only
                # (parent.name == "done" → idempotent file move, only fm updated)
                todo.move_to_done(sprint_id=sprint_id)
                repairs.append(f"moved TODO {todo_file.name} to done/")
```

### _close_sprint_legacy — same changes (around lines 820-855)

Apply the identical three-part restructure to `_close_sprint_legacy`:
- Scan `<sprint>/issues/` top-level (with move-to-done self-repair).
- Scan `<sprint>/issues/done/` (pass cleanly).
- Pending-pool: inline relocation to `<sprint>/issues/done/`.

### tests/unit/test_artifact_tools.py — new tests

Add a test class `TestCloseSprintIssuePreconditions` (or extend existing):

- `test_close_full_done_dir_issues_pass_cleanly`: put an issue in `<sprint>/issues/done/` with `status: done`; close succeeds without that issue appearing in repairs.
- `test_close_full_top_level_done_issue_migrated`: put an issue at `<sprint>/issues/` top level with `status: done`; verify close succeeds and issue is now in `issues/done/`.
- `test_close_full_inprogress_issue_hard_fails`: put an issue at `<sprint>/issues/` with `status: in-progress`; verify close returns an error result.
- `test_close_full_pending_pool_done_issue_relocated`: put a done-tagged issue in `.clasi/issues/` with `sprint == sprint_id`; verify close succeeds and issue lands in `<sprint>/issues/done/`.
- Mirror all four tests for `_close_sprint_legacy` path (call `close_sprint` without `branch_name`).

## Testing

- **Files to run**: `tests/unit/test_artifact_tools.py`
- **Verification command**: `uv run pytest tests/unit/test_artifact_tools.py -x` then `uv run pytest`
