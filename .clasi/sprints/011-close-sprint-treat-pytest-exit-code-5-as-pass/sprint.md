---
id: '011'
title: close_sprint treat pytest exit code 5 as pass
status: planning-docs
branch: sprint/011-close-sprint-treat-pytest-exit-code-5-as-pass
use-cases:
  - SUC-001
issues:
  - close-sprint-fails-on-pytest-exit-code-5.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 011: close_sprint treat pytest exit code 5 as pass

## Goals

Treat pytest exit code 5 ("no tests collected") as a passing test result in
`_close_sprint_full`, so that `close_sprint` succeeds in repos that have no
test suite.

## Problem

`_close_sprint_full` in `clasi/tools/artifact_tools.py` checks
`if test_result.returncode != 0:` to detect test failures. Pytest exit code 5
means "no tests were collected" — this is normal for repos without a test
suite, not a failure. When this fires, close_sprint returns an error, the
agent loses context, and subsequent retries arrive with empty `{}` arguments,
making the parameter-drop look like the root cause when it is only a secondary
symptom.

## Solution

Change the exit-code guard in `_close_sprint_full` to treat exit codes 0 and 5
as passing. Add a comment explaining the exit-code semantics. Add a unit test
confirming exit code 5 is treated as pass.

## Success Criteria

- `close_sprint` succeeds when the pytest process exits with code 5.
- A unit test asserts the exit-code 5 pass path.
- No regression in the exit-code 0 (pass) or non-zero/non-5 (fail) paths.

## Scope

### In Scope

- Change exit-code guard in `_close_sprint_full` (`clasi/tools/artifact_tools.py` line 1357).
- Add inline comment explaining pytest exit codes 0 and 5.
- Add unit test for exit code 5.

### Out of Scope

- Changes to close-sprint skill instructions or docstrings beyond the inline comment.
- Changes to any other sprint lifecycle step.

## Test Strategy

Unit test `_close_sprint_full` (or its subprocess path) with a mocked
subprocess result returning exit code 5 and verify it does not produce a
test-failure error response. Verify exit codes 0 (pass) and 1 (fail) remain
unchanged.

## Architecture Notes

Single-line logic fix in the artifact_tools module with a corresponding unit
test. No module boundaries change.

## GitHub Issues

(none)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Fix pytest exit-code 5 treated as pass in _close_sprint_full | — |

Tickets execute serially in the order listed.
