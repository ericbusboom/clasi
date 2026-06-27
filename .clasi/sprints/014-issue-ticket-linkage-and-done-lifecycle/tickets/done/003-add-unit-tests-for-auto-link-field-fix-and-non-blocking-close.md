---
id: '003'
title: Add unit tests for auto-link field fix and non-blocking close
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
- '002'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add unit tests for auto-link field fix and non-blocking close

## Description

Tickets 001 and 002 fix two defects in `clasi/tools/artifact_tools.py`. This
ticket adds unit tests to verify both fixes and prevent regression. Tests go in
the existing test files identified in the sprint success criteria.

## Acceptance Criteria

- [x] New test case in `tests/unit/test_issue_lifecycle.py` (or `test_issue_tools.py`): `create_ticket` with no `issue=` argument and a sprint that has `issues: [filename]` in frontmatter results in the ticket being linked to that filename.
- [x] New test case: `create_ticket` with no `issue=` argument and a sprint that has only `todos: [filename]` (no `issues:` field) still auto-links via the fallback.
- [x] New test case in `tests/unit/test_sweep_done_issues.py` (or `test_mcp_server.py`): `close_sprint` (full path) with an in-progress unresolved sprint issue returns a success result (not an error) and includes `unresolved_issues` in the result.
- [x] New test case: `close_sprint` (full path) with a deferred issue still closes cleanly (deferred-issue guard still works).
- [x] Full test suite passes: `pytest tests/unit/test_sweep_done_issues.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_mcp_server.py -q`
- [x] `pytest -q` (full suite) passes.

## Implementation Plan

### Approach

Read the existing test files first to understand fixtures and patterns before
writing new tests. Match the existing style (fixtures, tmp_path, etc.).

**For the auto-link field fix (A1):**
Add tests that construct a sprint fixture with `issues:` in the sprint.md
frontmatter (not `todos:`), call `create_ticket` without `issue=`, and assert
the resulting ticket has `issue:` set. Also add a test where only `todos:` is
present to verify the legacy fallback.

**For the non-blocking close (A2):**
Add tests that call the close path with an in-progress sprint issue present.
Assert the return value has `status: "success"` (not `"error"`) and that the
result dict contains `unresolved_issues` with the filename. Also assert the
deferred-issue path is unaffected.

### Files to Modify

- `tests/unit/test_issue_lifecycle.py` — add A1 test cases (auto-link reads
  `issues:`; legacy fallback to `todos:`).
- `tests/unit/test_sweep_done_issues.py` — add A2 test cases (non-blocking
  close with unresolved issue; deferred issue still passes).

If the existing files do not have appropriate fixtures for these cases, create
minimal fixtures inline in the new test functions. Do not refactor existing
fixtures.

### Testing Plan

- Run targeted suite after adding tests:
  `pytest tests/unit/test_sweep_done_issues.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_mcp_server.py -q`
- Run full suite: `pytest -q`

### Documentation Updates

None.
