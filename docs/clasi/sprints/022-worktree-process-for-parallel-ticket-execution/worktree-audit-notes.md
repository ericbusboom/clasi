<!--
WORKTREE AUDIT NOTES — Sprint 022, Ticket 001
Produced by ticket 001 as input for ticket 002 (design document).
Do not treat this as a formal document; it is a working reference only.
-->

# Worktree Audit Notes

## What was searched

Terms: `worktree`, `parallel`, `EnterWorktree`, `ExitWorktree`
Directories: `clasi/` and `docs/clasi/`
Excluded: `.venv/`, `__pycache__/`, build artifacts

---

## References in `clasi/` (source code and installed schemas)

### 1. `clasi/schemas/se-process/instructions/execution.md`

Context: **Active instruction** — the execute-sprint skill definition consumed
by the team-lead agent.

Relevant lines:

- Lines 7–10: "This skill is **strictly serial**. There is no parallel mode and
  no worktree usage. Re-enabling parallel/worktree execution is a future
  project; see
  `docs/clasi/todo/define-proper-worktree-process-for-parallel-ticket-execution.md`."
- Line 31: "There are no execution groups. Tickets run one at a time."
- Lines 54–56: "**Do not** invoke a second programmer agent until the first has
  returned. Do not create git worktrees. Do not branch off the sprint branch."

Nature: **Behavioral (prohibitive)**. This is the live enforcement of the
serial-only mandate. It is the canonical active reference.

### 2. `clasi/cli.py` (line 291)

Context: **Active source code** — the CLI's `fire-hook` command help text.

Relevant line:

    task-created         TaskCreated: log parallel-task lifecycle start.

Nature: **Narrative only** (a log-event label string). "parallel-task" refers
to the Claude Agent SDK's Task primitive, not to worktree-based parallel ticket
execution. No worktree logic is invoked here.

### 3. `clasi/plugin/agents/old/sprint-executor/execute-ticket.md`

Context: **Archived** — lives under `clasi/plugin/agents/old/`, a directory for
historical agent definitions that are no longer installed or active.

Relevant section (lines 118–136): "Parallel Execution Note" — describes that
this skill may be invoked inside a git worktree (`../worktree-ticket-NNN`) when
the project-manager has opted into parallel execution via a `parallel-execution`
skill. References a `worktree-protocol` instruction (which no longer exists —
deleted when parallelism was disabled).

Nature: **Historical narrative only**. These are archived docs. The parallel
path described here was disabled and this file is not active.

### 4. `clasi/plugin/agents/old/project-architect/agent.md` (line 77)

Context: **Archived** — same `old/` directory as above.

Relevant line: "Which TODOs are independent and could be done in parallel"

Nature: **Narrative only** (general analytical language, not worktree-specific).
No behavioral logic.

### 5. `clasi/plugin/instructions/git-workflow.md` (lines 91–92)

Context: **Active instruction** — the git-workflow reference consumed by agents.

Relevant lines: "Use this when multiple people or agents work in parallel, or
when you want PR-based review." (Appears in the section on per-ticket branches,
not in the sprint-branch section.)

Nature: **Narrative only** (describes a branch strategy option). No worktree
logic. Minimal reference; no change needed per the disable TODO.

---

## References in `docs/clasi/` (planning artifacts)

### 6. `docs/clasi/todo/in-progress/define-proper-worktree-process-for-parallel-ticket-execution.md`

Context: **Active TODO** — currently in-progress, owned by sprint 022.

Nature: **Narrative (planning artifact)**. This is the source TODO that spawned
sprint 022. It describes the gap (no authoritative worktree lifecycle spec) and
the deliverable (a concrete process and implementation plan). No behavioral logic.

### 7. `docs/clasi/todo/done/plan-todo-disable-parallel-ticket-execution-and-worktrees-force-serial-only.md`

Context: **Done TODO** — the decision record for the serial-only mandate.

Nature: **Narrative (decision record)**. Documents why parallel execution was
disabled (race conditions on commits and test suite; unreliable worktree
lifecycle). Lists files that were modified or deleted as part of the disable
effort. Key evidence: `clasi/plugin/instructions/worktree-protocol.md` was
deleted; `parallel-execution/SKILL.md` was deleted.

### 8. `docs/clasi/todo/done/sprint-owns-branch-and-worktree-lifecycle.md`

Context: **Done TODO** — implemented in sprint 002, ticket 010.

Nature: **Narrative (historical)**. Describes that the Sprint class should own
branch/worktree lifecycle methods. Implemented as `Sprint.create_branch()`,
`Sprint.merge_branch()`, `Sprint.delete_branch()` — no worktree methods were
added (the TODO was partially scoped to branch-only in the sprint).

### 9. `docs/clasi/sprints/done/002-task-lifecycle-hooks-and-refactoring/tickets/done/010-sprint-owns-branch-and-worktree-lifecycle.md`

Context: **Done ticket** — historical record of sprint 002 ticket 010.

Nature: **Narrative (historical)**. Acceptance criteria all concern branch
methods, not worktree methods. The worktree language in the title and TODO
was not implemented. No worktree code exists today.

### 10. Done sprint `sprint.md` files (sprints 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 017, 020, 021)

Context: **Archived sprint records**.

Nature: **Narrative only**. Most references are the old "parallel execution
group" language in ticket tables (e.g., "Tickets in the same Group can execute
in parallel"). This language was removed from active templates when parallelism
was disabled. These are done sprints; their sprint.md files are historical
records, not active instructions.

### 11. `docs/clasi/reflections/active-todo-queue-analysis.md`

Context: **Active reflection document**.

Nature: **Narrative only**. Discusses the worktree-process TODO as a planning
artifact in the context of prioritizing the TODO queue. Recommends deferring or
reframing the TODO given that parallel execution is currently disabled.

### 12. `docs/clasi/reflections/done/2026-04-01-tickets-not-moved-to-done.md`

Context: **Done reflection**.

Nature: **Narrative only**. References the `TaskCompleted` hook "merges the
worktree branch" — describes the old parallel path behavior that is no longer
active. Historical record.

### 13. `docs/clasi/todo/later/multi-agent-system-best-practices-research-compilation.md`

Context: **Later TODO** — deferred research task.

Nature: **Narrative only**. General multi-agent system guidance referencing
worktrees and parallelism in abstract best-practice terms. Not a CLASI worktree
implementation reference.

### 14. Sprint 022 planning artifacts (sprint.md, architecture-update.md, tickets)

Context: **Active** — the sprint currently being executed.

Nature: **Narrative/planning**. These documents describe what sprint 022 will
produce. The architecture-update.md is the primary reference for what the
design document and stub module should contain.

---

## Confirmation: Serial-only mandate is active

Read `clasi/schemas/se-process/instructions/execution.md` in full (2026-05-07).

**Finding**: The serial-only mandate is active and explicit. The document states:
"This skill is **strictly serial**. There is no parallel mode and no worktree
usage." Tickets run one at a time in dependency order, directly on the sprint
branch. No worktree creation is permitted.

**Finding**: `clasi/worktree.py` does not exist. There is no worktree module in
the `clasi/` package. The only references to worktrees in active source code are
the prohibitive language in execution.md (mandating no worktrees) and the
`task-created` log label in cli.py (unrelated to worktree execution).

---

## Summary for ticket 002

The worktree-related code surface is minimal:

| Location | Status | Nature |
|----------|--------|--------|
| `clasi/schemas/se-process/instructions/execution.md` | Active | Behavioral (serial-only mandate, prohibits worktrees) |
| `clasi/cli.py` line 291 | Active | Log label only, unrelated to worktree execution |
| `clasi/plugin/agents/old/sprint-executor/execute-ticket.md` | Archived | Historical narrative describing old parallel path |
| `clasi/plugin/agents/old/project-architect/agent.md` | Archived | General narrative |
| `clasi/plugin/instructions/git-workflow.md` | Active | Minimal narrative, no worktree logic |
| All `docs/clasi/` references | Archive/planning | Narrative only |

No `clasi/worktree.py` exists. No active code implements or supports worktree
operations. The deleted files (`worktree-protocol.md`,
`parallel-execution/SKILL.md`) have no surviving implementations.

Ticket 002 can design the worktree-process document with confidence that it will
not conflict with any existing behavioral logic. The stub module created in
ticket 003 will be the first code to carry the worktree concept in the active
source tree.
