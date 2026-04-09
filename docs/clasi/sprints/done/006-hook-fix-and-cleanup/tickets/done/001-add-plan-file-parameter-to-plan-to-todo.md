---
id: '001'
title: Add plan_file parameter to plan_to_todo()
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
todo: fix-plan-to-todo-hook-agent-ignores-do-not-implement-instruction.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add plan_file parameter to plan_to_todo()

## Description

Add an optional `plan_file: Optional[Path] = None` parameter to `plan_to_todo()` in `clasi/plan_to_todo.py`. When provided, use that specific file directly instead of scanning `plans_dir` for the newest `.md` by mtime. Fall back to the mtime heuristic when `plan_file` is `None`.

This is the foundational change that enables `handle_plan_to_todo()` (in ticket 002) to pass the exact plan file path received from the hook payload.

## Acceptance Criteria

- [x] `plan_to_todo()` signature is `plan_to_todo(plans_dir, todo_dir, hook_payload=None, plan_file=None)`.
- [x] When `plan_file` is provided and exists, it is read directly (no glob of `plans_dir`).
- [x] When `plan_file` is provided and does not exist, function returns `None`.
- [x] When `plan_file` is `None`, behavior is identical to Sprint 005 (mtime heuristic).
- [x] The provided `plan_file` is deleted after successful conversion (same as the mtime-found file).
- [x] `uv run pytest tests/unit/test_plan_to_todo.py -v` passes.

## Implementation Plan

### Approach

Modify `plan_to_todo()` in `clasi/plan_to_todo.py` to accept and use the explicit path before falling back to the glob.

### Files to Modify

**`clasi/plan_to_todo.py`**:
- Change signature to add `plan_file: Optional[Path] = None` after `hook_payload`.
- After the `if not plans_dir.is_dir()` check, add:
  ```python
  if plan_file is not None:
      if not plan_file.exists():
          return None
  else:
      plan_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
      if not plan_files:
          return None
      plan_file = plan_files[-1]
  ```
- Replace the existing `plan_file = plan_files[-1]` line and the surrounding glob/sort/check block with the above.
- The remainder of the function (`content = plan_file.read_text(...)` onward) is unchanged.

Note: the `plans_dir.is_dir()` guard must remain -- it short-circuits when there is no plans directory at all (even if `plan_file` is given, we keep this guard for the fallback path; or move it into the else branch if `plan_file` is given independently).

Revised structure:
```python
def plan_to_todo(
    plans_dir: Path,
    todo_dir: Path,
    hook_payload: Optional[dict] = None,
    plan_file: Optional[Path] = None,
) -> Optional[Path]:
    if plan_file is not None:
        if not plan_file.exists():
            return None
    else:
        if not plans_dir.is_dir():
            return None
        plan_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
        if not plan_files:
            return None
        plan_file = plan_files[-1]

    content = plan_file.read_text(encoding="utf-8").strip()
    ...
```

### Tests to Write

In `tests/unit/test_plan_to_todo.py`, add a new class `TestPlanToTodoPlanFileParam`:

1. `test_uses_plan_file_when_provided` -- create two `.md` files in `plans_dir` (one older, one newer); pass the older one as `plan_file`; verify the result uses the older file's title/slug, not the newer one.
2. `test_plan_file_is_deleted_after_conversion` -- pass a specific file; verify it is deleted after `plan_to_todo()` returns.
3. `test_returns_none_when_plan_file_missing` -- pass a non-existent `Path`; verify `None` is returned.
4. `test_falls_back_to_mtime_when_plan_file_none` -- call with `plan_file=None`; verify the newest file is used (existing behavior, regression check).
5. `test_plan_file_ignores_plans_dir_when_provided` -- call with `plan_file` pointing to a file outside `plans_dir`; verify it works (demonstrates plans_dir is not required when plan_file is given).

### Documentation Updates

None required -- this is an internal function. The architecture update already documents the new signature.
