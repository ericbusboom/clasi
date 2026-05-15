---
id: '002'
title: Rename docstring prose from todo to issue
status: done
use-cases:
- SUC-002
depends-on:
- '001'
issue: finish-the-todo-issue-rename.md
---

## Description

Update docstring and inline-comment prose that still uses "TODO" as the
CLASI artifact noun. All changes are text-only; no executable logic changes.

Files in scope (exact locations from the issue audit):
- `clasi/issue.py:15` — `Issue` class docstring
- `clasi/plan_to_issue.py:33` — `plan_to_issue` function docstring
- `clasi/hook_handlers.py:858, 863, 867, 894, 915` — five prose locations

## Acceptance Criteria

- [x] `Issue` class docstring (`issue.py:15`) no longer says `docs/clasi/todo/`; updated to `.clasi/issues/` or `<sprint>/issues/` consistent with the current model
- [x] `plan_to_issue` docstring first line (`plan_to_issue.py:33`) updated from "Copy a plan file to the TODO directory" to "Copy a plan file to the issue directory"
- [x] `hook_handlers.py:858` section heading comment updated (removes "Plan-to-TODO")
- [x] `hook_handlers.py:863` docstring updated (removes "CLASI TODO" as artifact noun)
- [x] `hook_handlers.py:867` prose updated
- [x] `hook_handlers.py:894` prose updated
- [x] `hook_handlers.py:915` prose updated
- [x] Backward-compat alias functions and registry keys at lines 890, 926, 980, 982 are untouched
- [x] Full test suite passes

## Implementation Plan

### Approach

Read each file, locate the exact lines listed, replace the prose. Confirm
the backward-compat block (lines 890, 926, 980, 982) is not touched.

### Files to Modify

- `clasi/issue.py` — class docstring only
- `clasi/plan_to_issue.py` — function docstring first sentence only
- `clasi/hook_handlers.py` — five inline prose locations; alias lines and
  registry keys below line 890 are out of scope

### Testing Plan

- Run `pytest tests/unit/` — docstring changes do not affect logic but
  confirm nothing was accidentally broken.
- Inspect diff: no executable lines modified, only string literals inside
  triple-quoted docstrings and comments.

### Documentation Updates

None. This ticket is itself documentation cleanup.
