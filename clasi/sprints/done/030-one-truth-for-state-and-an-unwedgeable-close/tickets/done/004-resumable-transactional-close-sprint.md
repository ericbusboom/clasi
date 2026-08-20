---
id: '004'
title: Resumable, transactional close_sprint
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: resumable-transactional-close-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Resumable, transactional close_sprint

## ⚠ Read this before touching any code

**This ticket rewrites the code that will close this very sprint.**
Sprint 030 will call `close_sprint("030")` shortly after this ticket (and
005, 006) land. Do not let that fact push you into over-engineering
defensive machinery beyond this ticket's actual scope — implement exactly
what the acceptance criteria below ask for, nothing more. Two safety
facts to hold onto while you work, not obstacles to design around:

1. **The current implementation is not catastrophic — it has closed 29
   sprints successfully**, including sprint 029's own. Its fragility is
   specifically on the *failure* path (a test failure or merge conflict
   mid-close), not the happy path. If something about your change is
   ambiguous, prefer the simpler interpretation that keeps the happy path
   working exactly as it does today.
2. **The manual recovery path is untouched by this ticket and remains
   available regardless of what you build.** `StateDB.recovery_state`,
   `clear_sprint_recovery`, and hand-editing per the `instruction` field
   `close_sprint` already returns on failure are not going anywhere. If
   your own testing of this ticket's changes leaves a sprint (a scratch
   one — see Testing below, never sprint 030 itself) in a half-closed
   state, that path is exactly how you get it back to a clean state. You
   are not the last line of defense.

**Do not restructure anything beyond this ticket's acceptance criteria.**
In particular: do not touch `set_sprint_stage()` (ticket 001, already
landed by the time you start this one — call it, don't re-derive it); do
not touch any `state_machine/` predicate file (ticket 002); do not touch
`ticket.py`'s done-transition (ticket 003, also already landed — call
`update_ticket_status`, don't duplicate its logic); do not start ticket
005's `@clasi_tool` decorator work early, even though this ticket's
`close_sprint` tool function is exactly what 005 will wrap next. Land
your fix, get it reviewed, then stop.

## Description

`close_sprint`'s state-transition handling was never designed for
failure. Per the reliability review and this repo's own code (verified
during planning, not assumed):

- The DB update is wrapped in `except (ValueError, Exception): pass`
  (`tools/artifact_tools.py:1811`, inside the current `_close_sprint_full`
  Step 4) — a failure there archives the sprint directory while the DB
  keeps the old phase **and the execution lock**, so the next
  `acquire_execution_lock` fails until someone hand-edits the DB.
- Step 5 (version bump, `artifact_tools.py:1859-1910`) has no "already
  bumped" check — a retry after a later step's failure re-runs it
  unconditionally, minting a second tag for the same close.
- `write_recovery_state` is called on every failure but `close_sprint`
  never reads it back on the next call (confirmed: no
  `get_recovery_state`/`db.recovery_state` read anywhere in
  `_close_sprint_full`).
- Self-repair (ticket move, issue relocation, DB phase catch-up) runs in
  Step 1, **before** the test gate in Step 2, with no rollback — a test
  failure after self-repair has already run leaves the repo in a state
  that never existed before the call.
- Tag push uses `git push --tags` (`artifact_tools.py:1980`), pushing
  every local tag, not just the sprint's own.

This ticket extracts the close orchestration into a new `close.py`
module (`SprintCloser`) with an ordered set of steps, each responsible
for its own idempotency check against ground truth, and moves self-repair
to after the test gate. See `sprint.md`'s Architecture M2 and Design
Rationale ("resumability via per-step idempotency against ground truth,
not a new 'completed steps' DB column" and "`close.py` is created now,
not patched in place").

## Acceptance Criteria

- [x] `StateDB.force_close(sprint_id)` (new method, `state_db_class.py`)
      sets `sprints.phase` to `"done"` and deletes the `execution_locks`
      row (if held by this sprint) in one transaction. It is idempotent:
      calling it against a sprint already at phase `"done"` with no lock
      held is a cheap no-op, not an error. Any failure is returned to the
      caller — no bare `except: pass`.
- [x] `close.py` (new top-level module) holds `SprintCloser`, the
      orchestration for: precondition check (read-only — see next
      bullet), tests, archive, DB update (`force_close`), design-overlay
      apply, version bump, git merge, tag push, branch delete, worktree
      prune.
- [x] **Precondition checking is read-only.** It reports what would need
      repair (a ticket not `done`, an issue not relocated, DB phase
      behind) without mutating anything. Self-repair mutations (moving a
      ticket/issue that is *already effectively done* but not yet
      relocated, catching the DB phase up) happen only **after** the test
      gate passes, and every mutation is recorded via
      `write_recovery_state` as it happens.
    - Note: with ticket 003 landed, `update_ticket_status(path, "done")`
      already keeps ticket frontmatter and location in sync going
      forward — so post-test repair should have materially less to do
      than the current code's Step 1. It is still needed as a safety net
      (a ticket moved by a legacy call path, or hand-edited), not
      removable.
- [x] The version-bump step checks whether the computed tag already
      exists in git (via the existing `_get_existing_tags`/
      `compute_next_version` machinery) before bumping — a retry after a
      later step's failure does not mint a second tag for an unchanged
      HEAD.
- [x] Every `run_git` call in the close sequence has its return code
      checked; a git failure fails the step loudly with the git output
      included in the error, not silently continuing.
- [x] The tag-push step pushes the sprint's own tag by name
      (`git push origin v{version}`), not `git push --tags`.
- [x] `tools/artifact_tools.py`'s `close_sprint` tool function becomes a
      thin wrapper delegating to `close.SprintCloser` — the ~950-line
      `_close_sprint_full` body moves to `close.py`, not duplicated.
- [x] A test simulates a failed close (kill the test step mid-close),
      then retries, and asserts: a single version tag exists (not two),
      the execution lock is released (not held by the archived sprint),
      and steps already completed on the first attempt are not
      meaningfully redone on the retry (verify via a spy/counter on the
      version-bump and test-run steps, not by re-running the actual test
      suite recursively).

## Implementation Plan

**Approach**: build `StateDB.force_close` first (small, testable in
isolation), then build `close.py`'s step sequence around it, porting
`_close_sprint_full`'s existing logic step-by-step rather than rewriting
from scratch — most of the git-call/archive/merge logic is already
correct (root-anchored since sprint 029) and should move, not be
redesigned. Reorder self-repair to after the test gate as part of the
port, not as a separate pass.

**Files to modify**:
- `src/clasi/state_db_class.py` — new `force_close`
- `src/clasi/close.py` (new) — `SprintCloser` and its step sequence
- `src/clasi/tools/artifact_tools.py` — `close_sprint` becomes a thin
  wrapper; `_close_sprint_full` and its helpers move to `close.py`

**Do not modify**: `sprint.py`'s `set_sprint_stage`/`detail_promote`/
`advance_phase` (ticket 001, already landed — call it), any
`state_machine/` file (ticket 002, already landed), `ticket.py`'s
done-transition (ticket 003, already landed — call
`update_ticket_status`), `tools/_common.py` or any `@clasi_tool`
application (ticket 005 — not started yet, do not begin it early).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block, not a silent allow. This
  matters more than usual for this ticket: if a guard blocks a git
  operation or a file write while you are testing your own close-sprint
  changes against a scratch sprint, that is the guard doing its job, not
  a bug to route around.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure — the stakeholder
  raised this explicitly for this sprint, and it applies with extra force
  here given what this ticket touches.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_close_sprint_auto_detect.py tests/unit/test_close_sprint_worktrees.py tests/unit/test_state_db_class.py tests/system/test_sprint_review.py tests/system/test_version_bump_cadence.py -v`
- **New tests to write**: `StateDB.force_close` idempotency and
  transactionality tests; a `close.py` step-runner test using a
  **scratch temporary sprint/project fixture** (never this repo's own
  sprint 030) that kills the test step mid-close and asserts the
  resumability properties in the last acceptance-criteria bullet above.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — not the full suite, and never a live
  `close_sprint("030")` call as part of this ticket's own verification.
  Closing sprint 030 for real is the team-lead's action after all six
  tickets are done, not something this ticket's own testing should
  attempt.
