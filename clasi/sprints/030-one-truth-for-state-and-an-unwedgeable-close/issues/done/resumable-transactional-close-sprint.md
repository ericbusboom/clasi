---
status: done
type: bug
tags:
- reliability-campaign
- phase-2
- mcp
- close-sprint
sprint: '030'
tickets:
- 030-004
---

# close_sprint: transactional state update, resumable steps, repairs after the test gate

## Description

The single most likely source of the "tool useless until hand-repair"
lockups. From the reliability review (00-review.md C3, C4, C5;
02-mcp-tools.md F1, F2, F9; 01-state-layer.md finding 1):

1. The DB update is wrapped in `except: pass` — a failed close archives the
   sprint directory while the DB keeps the old phase and the execution
   lock; the next sprint cannot start.
2. Retry re-runs the version bump (double tags), and `git add`/`git commit`
   return codes are ignored, so tags can land on the wrong commit with the
   cause hidden. `close_sprint` writes recovery state on failure but never
   reads it.
3. The "self-repair" step mutates tickets/issues/phases before the test
   gate, with no rollback and no `unclose_sprint`.
4. `git push --tags` pushes all local tags instead of the sprint's tag.

## Acceptance criteria

- A transactional `StateDB.force_close(sprint_id)` sets phase to done and
  releases the lock in one step; any failure is surfaced in the tool
  result, never swallowed.
- On retry, `close_sprint` reads its recovery state and skips completed
  steps — tests do not re-run for an unchanged HEAD, the version bump runs
  at most once per sprint.
- Self-repair is read-only before the test gate; mutations happen only
  after tests pass, and every file move is recorded in recovery state.
- Git failures in the bump/tag/merge sequence fail the step loudly with
  the git output; only the sprint's own tag is pushed.
- A test simulates a failed close and asserts: lock released or held
  correctly per the failure point, no double tag on retry, resumption
  skips completed steps.
