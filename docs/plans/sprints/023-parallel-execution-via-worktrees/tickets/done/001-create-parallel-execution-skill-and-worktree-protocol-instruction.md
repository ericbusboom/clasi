---
id: "001"
title: "Create parallel-execution skill and worktree-protocol instruction"
status: done
use-cases: [SUC-001, SUC-002]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create parallel-execution skill and worktree-protocol instruction

## Description

Create two new content files that enable parallel ticket execution
within a sprint using git worktrees for isolation:

1. **skills/parallel-execution.md** — Defines the full parallel
   execution workflow:
   - **Independence analysis**: How to determine which tickets can run
     in parallel (no overlapping file modifications, no dependency edges
     between them). Tickets with `depends-on` relationships or shared
     target files must be sequential.
   - **Worktree creation**: Create a git worktree per independent ticket
     so each subagent works in full filesystem isolation.
   - **Dispatch**: Use the dispatch-subagent skill (from sprint 022) to
     send each ticket to a subagent in its worktree.
   - **Review**: Apply two-stage review to each subagent's output.
   - **Merge**: Merge each worktree branch back to the sprint branch.
   - **Cleanup**: Remove worktrees after successful merge.

2. **instructions/worktree-protocol.md** — Defines the operational
   rules for worktree management:
   - **Naming**: Worktree directories named `worktree-ticket-NNN`,
     branches named per ticket within the sprint.
   - **Cleanup**: Worktrees must be removed after merge — never left
     dangling.
   - **Conflict resolution**: If merge conflicts occur, stop parallel
     execution and fall back to sequential for the conflicting tickets.
     Report the conflict to the controller for manual resolution.

MUST read Superpowers `dispatching-parallel-agents.md` and
`using-git-worktrees.md` for details on worktree-based parallelism
patterns and conflict handling.

## Acceptance Criteria

- [x] `skills/parallel-execution.md` exists and defines the full parallel workflow
- [x] Independence analysis criteria are specific (file overlap check, dependency graph check)
- [x] `instructions/worktree-protocol.md` exists and defines naming, cleanup, and conflict rules
- [x] Naming convention is `worktree-ticket-NNN`
- [x] Conflict resolution falls back to sequential execution
- [x] Skill references dispatch-subagent and worktree-protocol

## Testing

- **Existing tests to run**: `uv run pytest` — skill listing and instruction listing tests must pick up the new files
- **New tests to write**: None required (content-only files, discovered by existing listing tests)
- **Verification command**: `uv run pytest`
