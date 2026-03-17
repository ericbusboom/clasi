---
id: "023"
title: "Parallel Execution via Worktrees"
status: active
branch: sprint/023-parallel-execution-via-worktrees
use-cases:
  - SUC-001
  - SUC-002
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 023: Parallel Execution via Worktrees

## Goals

Enable parallel ticket execution within a sprint by using git worktrees
for isolation. Independent tickets (no shared files, no dependencies)
can be executed concurrently by separate subagents, each in its own
worktree.

## Problem

CLASI's execution model is strictly sequential: one ticket at a time.
For sprints with multiple independent tickets, this serializes work
unnecessarily. The execution lock prevents concurrent sprints (by
design), but there's no mechanism for concurrent tickets within a sprint.

## Solution

1. **Parallel execution skill** — Defines the workflow: analyze sprint
   tickets for independence (no overlapping file modifications, no
   dependency chain), create worktrees per independent ticket, dispatch
   subagents (using dispatch-subagent from sprint 022), collect results,
   review, merge worktree branches back.

2. **Worktree protocol instruction** — Rules for worktree management:
   naming convention, cleanup after merge, conflict resolution if
   worktrees unexpectedly touch the same file.

This is optional and explicit — sequential execution remains the safe
default. The stakeholder or project-manager must opt in to parallel mode.

Depends on sprint 022 (subagent dispatch) being completed first.

Reference: Read Superpowers `dispatching-parallel-agents.md` and
`using-git-worktrees.md`.

## Success Criteria

- Parallel execution skill defines independence analysis and worktree workflow
- Worktree protocol instruction defines naming, cleanup, conflict resolution
- Sequential remains default; parallel is opt-in
- execute-ticket notes parallel option
- project-manager has parallel dispatch guidance

## Scope

### In Scope

- New skill: `parallel-execution.md`
- New instruction: `worktree-protocol.md`
- Modify skill: `execute-ticket.md` (note about parallel option)
- Modify agent: `project-manager.md` (parallel dispatch guidance)

### Out of Scope

- Changes to execution lock or state_db.py
- Automatic parallelism detection (agent must analyze manually)
- Cross-sprint parallelism

## Test Strategy

Content-only sprint. Verification:
- `uv run pytest` (no regressions)
- Manual review of skill and instruction content

## Architecture Notes

This sprint adds an optimization layer on top of the dispatch system
from sprint 022. The Agent tool with `isolation: "worktree"` parameter
provides the worktree mechanism — no custom Python code needed.

The execution lock remains at sprint level. Ticket-level parallelism
is managed by the agent within the sprint's execution phase.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001** — Create parallel-execution skill and worktree-protocol instruction
   - use-cases: SUC-001, SUC-002 | depends-on: none
2. **002** — Update project-manager and execute-ticket with parallel option
   - use-cases: SUC-001 | depends-on: 001
