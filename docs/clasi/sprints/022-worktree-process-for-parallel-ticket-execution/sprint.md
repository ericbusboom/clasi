---
id: "022"
title: "Worktree process for parallel ticket execution"
status: roadmap
branch: sprint/022-worktree-process-for-parallel-ticket-execution
use-cases: []
source-todos:
  - define-proper-worktree-process-for-parallel-ticket-execution.md
---

# Sprint 022: Worktree process for parallel ticket execution

## Goals

Define and implement a proper, end-to-end worktree lifecycle for parallel
ticket execution in CLASI so that — when parallel execution is eventually
re-enabled — the process has one clear source of truth for how worktrees are
created, used, validated, merged, recovered, and cleaned up.

**PRIORITY / DEFERRAL NOTE**: Recent commit `chore: disable parallel ticket
execution and worktrees, mandate serial-only` has turned off parallel execution
entirely. This sprint should not be scheduled until the team decides to
re-enable parallelism. It is captured here as a roadmap entry for when that
decision is made, not as near-term work. Mark as LOW PRIORITY / DEFERRED at
stakeholder review.

## Problem

CLASI documented a worktree-based parallel ticket flow, but the actual
lifecycle was not defined strongly enough to make the path reliable. Ambiguities
existed around:

- When parallel execution is allowed vs. when CLASI must fall back to serial.
- How ticket independence is determined (shared-file and shared-test hazards).
- Who owns worktree creation, per-ticket branch creation, merge-back, cleanup.
- Naming conventions for worktrees and ticket branches.
- Validation required before a ticket is considered complete.
- Handling of merge conflicts, dirty trees, failed tests, abandoned worktrees.
- Which hooks log vs. which controller code enforces state transitions.
- What audit trail or recovery state must be recorded for diagnostics and
  resumability.

Because these questions were unresolved, parallel execution was disabled
(serial-only mandate). This sprint defines the answers and implements the
resulting process.

## Solution outline

- Author a process document (`docs/clasi/design/worktree-process.md`) that
  answers all the enumerated questions: preconditions, lifecycle states,
  naming conventions, merge strategy, conflict resolution, cleanup, recovery.
- Implement the controlling code: worktree creation, per-ticket branch setup,
  pre-completion validation, merge-back, cleanup.
- Define the audit trail / recovery state schema (what gets written, where,
  who reads it on recovery).
- Update `EnterWorktree` / `ExitWorktree` tool behavior to enforce the process.
- Gate parallel execution behind an explicit opt-in flag or config key so it
  cannot be accidentally re-enabled.

## Success criteria

- A process document exists specifying the full worktree lifecycle with no
  ambiguous steps.
- Worktree creation, merge-back, and cleanup are implemented and tested.
- Ticket independence checking (shared-file and shared-test hazard detection)
  is implemented.
- Recovery state is recorded in a defined location; a failed worktree session
  can be diagnosed and resumed from that state.
- Parallel execution requires explicit opt-in; serial execution remains the
  default and is unaffected by this sprint's changes.
- The existing serial execution path passes the full test suite without
  regression.

## In Scope

- `docs/clasi/design/worktree-process.md`: the authoritative process document.
- Worktree lifecycle implementation (creation, naming, branch setup,
  merge-back, cleanup) in the relevant CLASI or clasr module.
- Ticket independence checking logic.
- Audit/recovery state schema and write/read paths.
- `EnterWorktree` / `ExitWorktree` enforcement updates.
- Tests covering the lifecycle (unit + integration where feasible).

## Out of Scope

- Re-enabling parallel execution by default. This sprint makes parallel
  execution correct; a separate decision re-enables it.
- General multi-agent strategy work not specific to worktree lifecycle.
- Re-planning sprint execution broadly beyond the worktree path.
- Removing the serial-only mandate. The mandate stays until stakeholder
  explicitly lifts it.

## Dependencies and sequencing

- LOW PRIORITY / DEFERRED. Do not schedule until the team decides to re-enable
  parallel ticket execution.
- No dependency on sprints 017-021. Fully independent in content.
- Should not run concurrently with any sprint that modifies the ticket
  execution controller or `EnterWorktree` / `ExitWorktree` tool behavior.
- Recommend revisiting this sprint's priority after sprint 020 (schema-driven
  workflow) lands, since the schema may influence how worktree lifecycle phases
  are declared.

## Source TODOs

- `docs/clasi/todo/define-proper-worktree-process-for-parallel-ticket-execution.md`

## Tickets

| # | Title | Depends On |
|---|-------|------------|
