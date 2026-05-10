---
status: done
sprint: '022'
tickets:
- 022-001
- 022-002
- 022-003
- 022-004
---

# Define Proper Worktree Process for Parallel Ticket Execution

## Description

CLASI currently documents a worktree-based parallel ticket flow, but the
actual lifecycle is not defined strongly enough to make that path reliable.
We need a proper, end-to-end worktree process for parallel execution so the
system has one clear source of truth for how worktrees are created, used,
validated, merged, recovered, and cleaned up.

This TODO is about defining the process and the owning abstractions, not about
removing the current parallel path. A separate effort can disable or narrow
parallelism while this work is being designed and implemented.

The process definition should cover at least:

- When parallel worktree execution is allowed vs. when CLASI must fall back to
  sequential execution
- How ticket independence is determined, including shared-file and shared-test
  hazards
- Who owns worktree creation, per-ticket branch creation, merge-back, and
  cleanup
- Required naming conventions for worktrees and ticket branches
- What validation must happen before a ticket is considered complete
- How merge conflicts, dirty trees, failed tests, and abandoned worktrees are
  handled
- What hooks are responsible for logging only vs. what controller code is
  responsible for enforcing state transitions
- What audit trail or recovery state must be recorded so failures are
  diagnosable and resumable

Deliverable: a concrete CLASI process and implementation plan that makes
worktree-based execution explicit, safe, and easier to reason about.

Out of scope:

- Removing or disabling current parallelism
- General multi-agent strategy work that is not specific to worktree lifecycle
- Re-planning sprint execution broadly beyond the worktree path