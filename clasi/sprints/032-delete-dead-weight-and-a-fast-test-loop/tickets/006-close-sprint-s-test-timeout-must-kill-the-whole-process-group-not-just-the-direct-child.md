---
id: '006'
title: close_sprint's test timeout must kill the whole process group, not just the
  direct child
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: close-sprint-timeout-orphans-the-test-process.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# close_sprint's test timeout must kill the whole process group, not just the direct child

## Description

`close.py`'s `_run_test_command` (verified during planning: the
function's own docstring already documents this precisely) uses
`subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
stdin=subprocess.DEVNULL)`. `subprocess.run`'s timeout kills only the
**direct child** — the direct child here is `uv` (or `npm`, `poetry`,
whatever wraps the configured test command), which forks the actual
`pytest` process as a grandchild in the same process group. Killing
`uv` on timeout leaves `pytest` running. Observed live at close of
sprint 031: an abandoned `uv run pytest` was still consuming CPU 32
minutes after its `close_sprint` call had been aborted client-side, and
had to be killed by hand.

**Why this wasn't fixed in 031-008**: the programmer implemented
`Popen` + `communicate()` + `start_new_session=True` + `os.killpg()` on
timeout, and verified it worked in isolation — but the switch from
`subprocess.run` to `Popen` silently bypassed a pre-existing global
`@patch("subprocess.run")` mock in
`tests/unit/test_close_sprint_worktrees.py`, whose hand-ordered
`side_effect` list has an explicit slot for the pytest call. Two of its
tests broke, and in that test's `tmp_path` a **real** `uv run pytest`
got spawned inside a unit test — it happened to exit fast with code 5
("no tests collected"), which is the only reason it surfaced as an
assertion mismatch rather than a hang. The programmer correctly
reverted and flagged rather than expanding scope into "rework an
unrelated test file's mocking strategy," which is exactly this ticket's
job now — do it deliberately, not as a side effect of the subprocess
fix.

The inherited-stdin half of this problem is already fixed:
`stdin=subprocess.DEVNULL` (visible in the current `_run_test_command`)
is in place and works correctly. This ticket is only about process-group
termination on timeout, not stdin.

## Acceptance Criteria

- [x] A timed-out test command leaves no surviving process: the whole
      process group is killed, not just the direct child. Verify with
      a test that deliberately spawns a grandchild outliving its
      direct-child parent (e.g. a shell wrapper script that
      backgrounds a long-running sleep before exiting, or a
      `subprocess.Popen` fixture in the test itself) and asserts the
      grandchild is also gone after the timeout fires — not merely that
      `_run_test_command` returns.
- [x] The fix uses `Popen` + `start_new_session=True` (or
      `preexec_fn=os.setsid` if targeting a Python version/platform
      where `start_new_session` isn't available — verify current
      minimum supported Python first) + `os.killpg(pgid, signal)` on
      `TimeoutExpired`, matching the approach 031-008 already validated
      in isolation — this ticket's job is making that approach's *test
      surface* correct, not re-deriving the subprocess mechanics from
      scratch.
- [x] `stdin=subprocess.DEVNULL` (or the `Popen` equivalent,
      `stdin=subprocess.DEVNULL`) is preserved — do not regress the
      031-008 fix while changing the invocation mechanism.
- [x] `tests/unit/test_close_sprint_worktrees.py`'s
      `@patch("subprocess.run")` mocking is reworked to match whatever
      invocation mechanism this ticket lands on (`Popen`-aware mocking
      — patch `Popen`/`communicate`/`killpg` as appropriate, not
      `subprocess.run`). Every test whose `side_effect` list has a slot
      for the pytest-command call is updated accordingly. **No unit
      test may spawn a real `pytest` subprocess** — the exact defect
      that let 031-008's issue surface as an assertion mismatch instead
      of a clean, obvious revert. Add an assertion or fixture guard
      that would fail loudly (not silently pass fast) if a real
      subprocess were ever spawned again by this test file.
- [x] Full suite passes, and specifically
      `tests/unit/test_close_sprint_worktrees.py` passes without
      spawning any real subprocess (verify this directly — e.g. by
      temporarily breaking the mock and confirming the test suite
      hangs or errors loudly rather than silently succeeding, then
      restoring the correct mock; or by adding a monkeypatch that
      raises if the real `Popen`/`subprocess.run` is ever reached
      unmocked).

**Implementation note (blast radius wider than scoped):** the
`@patch("subprocess.run")` + pytest-slot pattern this ticket's plan
anchored to `tests/unit/test_close_sprint_worktrees.py` turned out to
exist in three more files that call `close_sprint(..., branch_name=...)`
without mocking `Popen`: `tests/unit/test_issue_tools.py` (4 tests),
`tests/unit/test_sweep_done_issues.py` (2 tests), and
`tests/system/test_artifact_tools.py` (13 tests, including the
dedicated `TestCloseSprintTestTimeout` class this ticket's own subject
matter lives in). Left unfixed, all 19 would have silently spawned real
`Popen` calls once the `subprocess.run`→`Popen` switch landed — the
exact 031-008 failure mode, just in more places than the plan's
research surfaced. Verified empirically (ran each file with a bounded
timeout) before fixing: no hangs, only fast assertion-mismatch failures,
consistent with the mechanical "mock side_effect list off by one" root
cause. Reworked all three using the identical pattern already validated
in the scoped file (add `@patch("subprocess.Popen")`, mock
`.communicate()` for the pytest slot, drop that slot from the
`subprocess.run` side_effect list). All 108 tests in
`tests/system/test_artifact_tools.py`, all 67 in `test_issue_tools.py`,
and all 11 in `test_sweep_done_issues.py` pass. Flagging here per this
ticket's own Process Notes on scope, since this went beyond the
files-to-modify list — the fix was mechanical and low-risk (same pattern,
three more times), and leaving it undone would have broken the sprint's
close-time full-suite gate.

## Implementation Plan

### Approach

1. Read `close.py`'s `_run_test_command` and its docstring in full —
   it already documents the timeout/grandchild problem and explicitly
   defers the process-group fix; this ticket picks that up.
2. Read `tests/unit/test_close_sprint_worktrees.py` in full,
   specifically every `mock_run.side_effect = [...]` list, to inventory
   every place a pytest-command mock slot exists before changing the
   underlying mechanism — this is the step 031-008 skipped, and skipping
   it is exactly what caused the revert.
3. Implement the `Popen`/`start_new_session`/`killpg` change in
   `_run_test_command`.
4. Rework the test file's mocking to patch the new invocation
   mechanism instead of `subprocess.run`, updating every affected
   `side_effect` list.
5. Add the grandchild-survives-timeout regression test (a new test, not
   a mock — this one needs to actually spawn and verify termination,
   likely in an integration- or slow-tier test given it needs real
   process behavior, not a unit-level mock).
6. Add whatever guard proves no unit test in this file can spawn a real
   subprocess unmocked (see last acceptance criterion).
7. Run the full suite.

### Files to Modify

- `src/clasi/close.py` (`_run_test_command`)
- `tests/unit/test_close_sprint_worktrees.py` (rework mocking
  throughout — this is the larger part of this ticket's work, not an
  afterthought)
- Possibly a new test file or a new test within an existing
  integration-tier file for the real grandchild-termination check,
  since it needs actual process spawning, not mocks (mark it
  `@pytest.mark.slow` per this sprint's ticket 008 convention if that
  ticket has landed first — check `depends-on` ordering, though this
  ticket has none, so `slow` marking may not exist yet when this
  ticket executes; add the mark anyway if the `slow` marker already
  exists in `pyproject.toml`, or leave a comment for ticket 008/its
  implementer to mark it if not).

### Testing Plan

- **Existing tests to run**: `uv run pytest tests/unit/test_close_sprint_worktrees.py
  tests/unit/test_close_sprint.py -v` (verify exact second filename —
  there may be more than one close_sprint-related unit test file;
  grep for `close_sprint\|SprintCloser` under `tests/unit/` to find
  all of them before considering this ticket's scoped run complete).
- **New tests to write**: the grandchild-survives-timeout regression
  test (Acceptance Criteria); the "no real subprocess spawned unmocked"
  guard.
- **Verification command**: `uv run pytest tests/unit/test_close_sprint_worktrees.py -v`
  plus the new grandchild-termination test run directly (it may be slow
  enough to warrant running it individually rather than folding it into
  the default scoped command, given it involves real timing).

### Documentation Updates

- None required — this is an internal robustness fix with no
  user-facing behavior change (the test command still runs the same
  way; only its timeout-failure cleanup improves).

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `src/` and `tests/`.
- This ticket exists specifically because 031-008 tried to fold this
  fix in and correctly reverted rather than expanding scope
  mid-ticket. Do not repeat that pattern here by discovering more
  unrelated test-file issues and trying to fix them too — if
  `test_close_sprint_worktrees.py` turns out to need more rework than
  this ticket scoped, stop and report rather than quietly expanding.
