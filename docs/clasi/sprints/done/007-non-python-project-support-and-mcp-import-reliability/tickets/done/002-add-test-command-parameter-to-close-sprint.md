---
id: '002'
title: Add test_command parameter to close_sprint
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
todo: hardcoded-pytest-blocks-non-python-projects.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add test_command parameter to close_sprint

## Description

`close_sprint` in `artifact_tools.py` hardcodes `uv run pytest` as the test
command. Non-Python projects (Java, JavaScript, etc.) that have `uv` installed
get spurious test failures when closing sprints. The existing `FileNotFoundError`
fallback only handles the case where `uv` is missing entirely.

This ticket adds a `test_command: Optional[str] = None` parameter to
`close_sprint` and threads it through `_close_sprint_full`. When `test_command`
is `None`, behavior is unchanged (runs `uv run pytest`). When it is `""`, the
tests step is skipped. When it is any other string, that command is run instead.
The close-sprint skill docs are updated to document the parameter.

## Acceptance Criteria

- [ ] `close_sprint` accepts a `test_command: Optional[str] = None` parameter.
- [ ] `_close_sprint_full` signature includes `test_command` and uses it in
  Step 2 (the test run block around line 923).
- [ ] `test_command=None` (default): runs `["uv", "run", "pytest"]` as before.
- [ ] `test_command=""` (empty string): skips the test step; no subprocess call;
  adds `"skipped tests (test_command='')"` to `repairs`.
- [ ] `test_command="npm test"` (example custom command): runs the provided
  string via `subprocess.run(..., shell=True)` with the same timeout and
  error-handling logic as the pytest path.
- [ ] `clasi/plugin/skills/close-sprint/SKILL.md` documents the `test_command`
  parameter with examples for Python, JS, and skip cases.
- [ ] All existing tests continue to pass.
- [ ] New unit tests cover the three `test_command` variants.

## Implementation Plan

### Approach

1. Read `close_sprint` and `_close_sprint_full` in `artifact_tools.py`
   (around lines 651 and 772) to understand the current signatures.
2. Add `test_command: Optional[str] = None` to `close_sprint`; pass it to
   `_close_sprint_full`.
3. Update `_close_sprint_full` signature to accept `test_command`.
4. In Step 2 (the `subprocess.run(["uv", "run", "pytest"], ...)` block around
   line 927):
   - If `test_command is None`: keep the existing `["uv", "run", "pytest"]`
     invocation (including the `FileNotFoundError` fallback).
   - If `test_command == ""`: skip subprocess; append
     `"skipped tests (test_command='')"` to `repairs`.
   - Otherwise: run `subprocess.run(test_command, shell=True, capture_output=True,
     text=True, timeout=300)` with the same error-handling flow.
5. Update `clasi/plugin/skills/close-sprint/SKILL.md` to document
   `test_command` with examples.

### Files to modify

- `clasi/tools/artifact_tools.py` — `close_sprint` and `_close_sprint_full`
- `clasi/plugin/skills/close-sprint/SKILL.md` — document the new parameter

### Files to create

None.

## Testing

- **Existing tests to run**: `uv run pytest tests/` — verify no regressions.
- **New tests to write** (in tests for `artifact_tools` or `close_sprint`):
  - `test_close_sprint_default_runs_pytest`: mock `subprocess.run`; assert
    called with `["uv", "run", "pytest"]`.
  - `test_close_sprint_empty_string_skips_tests`: assert subprocess not called;
    result contains skip in repairs.
  - `test_close_sprint_custom_command_runs_it`: pass `test_command="npm test"`;
    assert subprocess called with `"npm test"` and `shell=True`.
- **Verification command**: `uv run pytest`
