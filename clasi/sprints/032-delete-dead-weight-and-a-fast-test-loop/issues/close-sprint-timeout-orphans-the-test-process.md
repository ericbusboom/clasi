---
status: in-progress
type: bug
tags:
- reliability-campaign
- close-sprint
- follow-up
sprint: '032'
tickets:
- 032-006
---

# close_sprint's test timeout kills only the direct child, orphaning the real pytest process

## Description

Found while closing sprint 031 (2026-08-21), alongside the inherited-stdin
hang fixed in ticket 031-008's follow-up pass.

When `close_sprint`'s test step times out — or when the MCP call is
aborted client-side — the actual pytest process survives and keeps
running indefinitely. Observed live: an abandoned `uv run pytest` was
still consuming CPU **32 minutes** after its `close_sprint` call had been
aborted, and had to be killed by hand. Nothing reaps it.

## Cause

`subprocess.run(..., timeout=N)` kills the **direct child** on
`TimeoutExpired`. The direct child here is `uv`, which spawns pytest as a
grandchild in the same process group. Killing `uv` leaves the grandchild
running. Since the test command is configurable and commonly a wrapper
(`uv run ...`, `npm test`, `poetry run ...`), the grandchild case is the
normal case, not the exception.

Compounding it: an aborted MCP call does not unwind the server-side call
at all, so the timeout may never even be reached.

## Why it was not fixed in 031-008

The programmer implemented the fix — `Popen` + `communicate()` +
`start_new_session=True` + `os.killpg()` on timeout — and verified it
worked in isolation. But switching from `subprocess.run` to `Popen`
silently bypassed a pre-existing global `@patch("subprocess.run")` mock
in `tests/unit/test_close_sprint_worktrees.py`, whose hand-ordered
`side_effect` list has an explicit slot for the pytest call. Two of its
tests broke, and in that test's `tmp_path` a **real** `uv run pytest` got
spawned inside a unit test — it happened to exit fast with code 5 ("no
tests collected"), which is the only reason it surfaced as an assertion
mismatch rather than a hang.

Making it robust requires reworking that file's mocking to be
`Popen`-aware, which crosses from "small, self-contained" into "changes
assumptions in an unrelated test file." The programmer reverted and
flagged it rather than expanding scope — the right call, and the reason
this issue exists.

## Acceptance criteria

- [ ] A timed-out test command leaves no surviving process: the whole
      process group is killed, not just the direct child. Verify with a
      command that deliberately spawns a grandchild which outlives its
      parent.
- [ ] `tests/unit/test_close_sprint_worktrees.py`'s mocking is reworked
      to match whatever invocation mechanism the fix uses, so no unit
      test can spawn a real test-suite subprocess. That a unit test was
      able to launch real pytest at all is its own small defect.
- [ ] Consider whether the same treatment is warranted for other
      long-running subprocesses in the close path.

## Related

- [[test-suite-predicate-registry-pollution]] — the other latent
  test-infrastructure issue from this campaign.
- The inherited-stdin half of this problem is already fixed: `close.py`'s
  test runner, `gitutil.run_git`, and `worktree.py`'s close-path git
  calls all now pass `stdin=subprocess.DEVNULL`.
