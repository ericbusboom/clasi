---
id: '001'
title: Fix pytest exit-code 5 treated as pass in _close_sprint_full
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: close-sprint-fails-on-pytest-exit-code-5.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix pytest exit-code 5 treated as pass in _close_sprint_full

## Description

`_close_sprint_full` in `clasi/tools/artifact_tools.py` checks
`if test_result.returncode != 0:` to decide whether the test run failed.
Pytest exit code 5 means "no tests were collected" — normal for repos
without a test suite. This code is incorrectly treated as a failure, causing
`close_sprint` to error and the calling agent to retry with empty arguments.

The fix is a one-line change to the guard plus a comment, and a new unit test.

## Acceptance Criteria

- [x] `clasi/tools/artifact_tools.py` line 1357: guard reads
      `if test_result.returncode not in (0, 5):`.
- [x] An inline comment above or on the same line explains that exit code 5
      means "no tests collected" (not a failure).
- [x] A new unit test mocks subprocess to return exit code 5 and asserts
      that `_close_sprint_full` does not return a test-failure error response.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

### Approach

Minimal targeted change: update the single guard expression, add a comment,
add a unit test.

### Files to Modify

- `clasi/tools/artifact_tools.py` — change guard at line 1357.

### Files to Create

- New test function in the existing test file for `artifact_tools` or
  `close_sprint` (locate with `grep -r "_close_sprint_full\|close_sprint"
  tests/` and add alongside existing tests).

### Code Change

```python
# Before (line 1357):
if test_result.returncode != 0:

# After:
# Pytest exit codes: 0=all passed, 1=some failed, 2=interrupted,
# 3=internal error, 4=usage error, 5=no tests collected.
# Exit code 5 is not a failure — repos with no test suite are fine.
if test_result.returncode not in (0, 5):
```

### Test to Add

```python
def test_close_sprint_full_treats_exit_code_5_as_pass(tmp_path, ...):
    """Pytest exit code 5 (no tests collected) must not be treated as failure."""
    # Mock subprocess.run to return exit code 5
    # Call _close_sprint_full (or the relevant helper) on a minimal sprint
    # Assert the response does not contain {"status": "error", "error": {"step": "tests"}}
```

Locate the best test module and fixture pattern by reading the existing
test files for `close_sprint` before writing the new test.

### Testing Plan

- Run `uv run pytest` to confirm all existing tests pass.
- Confirm the new test is collected and passes.

### Documentation Updates

None beyond the inline comment added to the source.
