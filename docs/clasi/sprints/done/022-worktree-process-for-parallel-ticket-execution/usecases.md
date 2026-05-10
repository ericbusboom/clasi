---
sprint: '022'
status: done
---

# Use Cases — Sprint 022: Worktree Process for Parallel Ticket Execution

## Scope Note

This sprint is **design-only**. Parallel ticket execution is currently disabled
by repo policy (see `clasi/schemas/se-process/instructions/execution.md`). No
behavior changes are introduced during this sprint. The deliverables are planning
artifacts — a worktree-process design document and a code-consolidation module —
that prepare the codebase to cleanly re-enable parallelism when the stakeholder
lifts the serial-only mandate.

---

## SUC-001: Authoritative worktree process reference

**Actor**: Future sprint planner or team-lead re-enabling parallel execution.

**Goal**: Consult a single document to understand the complete worktree lifecycle
without reading scattered code comments, old agent files, or commit messages.

**Preconditions**: The stakeholder has decided to investigate or re-enable parallel
ticket execution.

**Main flow**:
1. Actor navigates to `docs/clasi/design/worktree-process.md`.
2. Actor reads the precondition checklist determining when parallel execution is
   allowed vs. when CLASI must fall back to serial.
3. Actor reads the lifecycle sections covering: ticket independence checking,
   worktree creation, per-ticket branch setup, pre-completion validation,
   merge-back, cleanup, and error recovery.
4. Actor has all the information needed to implement or review the parallel path
   without consulting any other document.

**Postconditions**: Parallel execution can be re-enabled against a well-specified
process with no ambiguous steps.

**Out of scope**: Actually re-enabling parallel execution; writing production code.

---

## SUC-002: Ticket independence assessment

**Actor**: Team-lead or future execute-sprint skill.

**Goal**: Determine before dispatch whether a set of tickets can safely run in
parallel (no shared-file or shared-test hazards).

**Preconditions**: A sprint with multiple `todo` tickets exists. The design
document specifies the independence criteria.

**Main flow**:
1. The design document (or a future implementation guided by it) lists the files
   each ticket intends to touch.
2. Any overlap in file paths or test modules is flagged as a shared-file hazard.
3. Tickets flagged with hazards are serialized; non-overlapping tickets may be
   parallelized.

**Postconditions**: Each parallel group contains only independent tickets; serial
fallback is triggered automatically when hazards are detected.

---

## SUC-003: Worktree lifecycle clarity — create through cleanup

**Actor**: A future programmer agent or controller executing a parallel ticket.

**Goal**: Follow a defined lifecycle (create worktree, branch, implement, validate,
merge, cleanup) without improvising any step.

**Main flow**:
1. Controller creates a worktree at a defined path using the specified naming
   convention.
2. A per-ticket branch is created inside that worktree following the naming
   convention.
3. Programmer agent implements the ticket inside the worktree.
4. Pre-completion validation runs (tests, lint, no dirty tree).
5. Ticket branch is merged back to the sprint branch using the specified merge
   strategy.
6. Worktree is removed and the ticket branch deleted according to cleanup rules.

**Postconditions**: No leftover worktrees; sprint branch contains the merged
changes; audit record is written.

---

## SUC-004: Error and recovery path coverage

**Actor**: Team-lead recovering a failed parallel execution.

**Goal**: Diagnose what happened and resume or roll back without manual git surgery.

**Main flow**:
1. A programmer agent fails mid-ticket (test failure, merge conflict, crash).
2. Team-lead reads the audit/recovery state file to see which worktrees were
   open, which branches were created, and what the last recorded lifecycle step
   was.
3. Team-lead follows the documented recovery procedure: either re-dispatch into
   the existing worktree or destroy and restart cleanly.

**Postconditions**: Sprint can continue or be cleanly abandoned without orphaned
worktrees or dangling branches.

---

## SUC-005: Single attachment point for worktree code

**Actor**: Future programmer implementing parallel execution.

**Goal**: Modify or enable worktree behavior by changing one module, not scattered
references across agent instructions and cli.py.

**Preconditions**: Existing scattered worktree references (old sprint-executor
agent docs, cli.py references) have been consolidated into `clasi/worktree.py`
(or a comparable dedicated module).

**Main flow**:
1. Programmer opens `clasi/worktree.py`.
2. All worktree lifecycle functions (create, branch, validate, merge, cleanup,
   audit-write, audit-read) are present in that module.
3. Programmer wires the opt-in flag to call this module's functions instead of
   the no-op serial path.

**Postconditions**: Parallel execution can be activated with minimal blast radius;
serial path is unaffected.

---

## SUC-006: No regression on serial execution path

**Actor**: Serial programmer agent running a normal sprint today.

**Goal**: Continue to execute tickets serially on the sprint branch with no
observable change.

**Preconditions**: Sprint 022 deliverables have been merged.

**Main flow**:
1. Team-lead runs `execute-sprint` skill.
2. Skill reads `execution.md`, which still mandates serial-only.
3. Tickets are dispatched one at a time on the sprint branch, same as before.
4. No worktree code is invoked.

**Postconditions**: Serial path is fully unaffected; full test suite passes.
