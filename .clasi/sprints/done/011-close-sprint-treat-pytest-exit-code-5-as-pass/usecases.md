---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 011 Use Cases

## SUC-001: close_sprint succeeds in repos with no test suite

- **Actor**: Agent executing close_sprint on a foreign repo that has no tests.
- **Preconditions**: Sprint is in a closeable state. The default test command
  (`pytest`) runs but collects no test items (exit code 5).
- **Main Flow**:
  1. Agent calls `close_sprint` with valid sprint parameters.
  2. `_close_sprint_full` runs the test command.
  3. Pytest exits with code 5 (no tests collected).
  4. The function treats exit code 5 as a passing result.
  5. Sprint close proceeds to the next step without error.
- **Postconditions**: `close_sprint` completes successfully; no error is
  returned for a missing test suite.
- **Acceptance Criteria**:
  - [ ] `close_sprint` returns a non-error response when pytest exits with code 5.
  - [ ] A unit test mocking subprocess to return exit code 5 asserts the
        pass path.
  - [ ] Existing behavior for exit code 0 (pass) and non-zero/non-5 (fail)
        is unchanged.
