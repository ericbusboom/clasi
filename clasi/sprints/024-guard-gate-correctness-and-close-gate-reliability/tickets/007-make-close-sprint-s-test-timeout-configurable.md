---
id: '007'
title: Make close_sprint's test timeout configurable
status: open
use-cases: [SUC-005]
depends-on: []
github-issue: ''
issue: close-sprint-test-timeout-hardcoded-300s-too-short.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Make close_sprint's test timeout configurable

## Description

`close_sprint` (in `src/clasi/tools/artifact_tools.py`, around line 1564)
hardcodes `timeout=300` for the test-suite run during sprint close. This
repo's own test suite runs roughly 460-525 seconds, so a normal, healthy
close of any CLASI sprint in this repo times out at the tests step —
`close_sprint` reports a false timeout failure even though the suite would
have passed given more time.

Fix: replace the hardcoded `timeout=300` with a configurable value — a
`test_timeout` parameter on `close_sprint` and/or a `.clasi/config.yaml`
key — with the default raised to something that actually fits a real
suite (900 seconds is a reasonable default given this repo's own
460-525s runtime), and support `0` meaning unlimited (no timeout). Surface
the effective timeout value in the error message whenever a timeout does
occur, so a future false-timeout report is self-diagnosing rather than
requiring someone to go read the source to find the hardcoded number.

## Acceptance Criteria

- [ ] `close_sprint`'s test-suite timeout is no longer hardcoded to 300;
      it is configurable via a `test_timeout` parameter and/or a
      `.clasi/config.yaml` key.
- [ ] The default timeout is raised to a value that fits a real suite run
      (900s is the suggested default, given this repo's own suite runs
      about 460-525s) — chosen and documented as a ticket-level
      implementation decision.
- [ ] Passing `0` (or the documented unlimited sentinel) disables the
      timeout entirely.
- [ ] When a timeout does occur, the error message names the timeout
      value that was in effect (e.g. "test command exceeded the
      configured 900s timeout"), not a bare "timed out" with no context.
- [ ] Regression: closing a sprint with a fast test command (completes
      well under the new default) still works exactly as before.
- [ ] New test: a deliberately-hung/sleep-based fake test command, with
      the timeout explicitly set low for the test (e.g. a few seconds),
      still trips the timeout and blocks the close, with the error
      message naming that low configured value.
- [ ] Full test suite passes (`uv run pytest --no-cov -q`).

## Implementation Plan

**Approach**: Locate the hardcoded `timeout=300` call site in
`close_sprint` (`src/clasi/tools/artifact_tools.py`, near line 1564),
thread a configurable value through: function parameter with a raised
default, falling back to a `.clasi/config.yaml` key if present, falling
back to the new hardcoded default otherwise. Update the timeout-exceeded
error path to include the effective value in its message.

**Files to modify**:
- `src/clasi/tools/artifact_tools.py` — `close_sprint`'s test-execution
  call site: add `test_timeout` parameter (or equivalent config lookup),
  raise the default, support `0` as unlimited, include the value in the
  timeout error message.
- Config schema/loading code, if a `.clasi/config.yaml` key is added
  (identify the existing config-loading module for this project and
  follow its established pattern rather than inventing a new one).

**Testing plan**:
- Existing tests to run: any existing `close_sprint` tests (regression —
  confirm the fast-test-command path still closes successfully with the
  new default).
- New tests:
  - Fast test command (e.g. `true` or an equivalent trivial success)
    closes successfully under the new default — regression check that
    raising the default didn't break the happy path.
  - Slow/hung test command (e.g. `sleep 30` or a Python script with a
    controllable sleep) with `test_timeout` explicitly set low for the
    test (e.g. 2-3 seconds) still trips the timeout, still blocks close,
    and the resulting error message names the configured timeout value
    used (not a generic message with no number).
- Verification command: `uv run pytest --no-cov -q`.

**Documentation updates**:
- Update `close_sprint`'s tool docstring/description to document the new
  parameter/config key, its default, and the unlimited (`0`) sentinel.
- If a `.clasi/config.yaml` key is added, document it wherever this
  project's other config keys are documented (e.g. a config reference
  doc, if one exists — locate it rather than assuming; if none exists,
  a brief note in the docstring may be sufficient).
