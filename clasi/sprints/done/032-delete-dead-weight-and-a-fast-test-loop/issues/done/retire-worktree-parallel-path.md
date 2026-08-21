---
status: done
type: task
tags:
- reliability-campaign
- phase-4
- deletion
sprint: '032'
tickets:
- 032-003
---

# Retire the worktree parallel path: delete about 1,700 lines still referenced by live instructions

## Description

From docs/reviews/2026-08-reliability/04-cli-install-platforms.md finding
F5 and its deletion table. `src/clasi/worktree.py` is 1,035 lines, of
which roughly 550 implement a parallel-execution lifecycle that has never
run:

- `create_worktree`, `create_ticket_branch`, `validate_worktree`,
  `merge_ticket_branch`, `check_independence`, plus seven parsing helpers
- No MCP tool exposes any of them — only `reconcile_worktrees` is exposed
- Every real sprint (022-030) carries `worktree: false`
- The module's own docstring says "Parallel execution is disabled… not
  yet wired into the controller"

Meanwhile `schemas/se-process/instructions/execution.md` spends about 175
of its 333 lines describing a live Parallel Path that instructs agents to
call those functions. An agent on a `worktree: true` sprint could only
comply by improvising `python -c` shell-outs. The `close-sprint` skill
separately claims `acquire_execution_lock` creates one worktree per
ticket, which it does not.

The stakeholder previously removed worktrees from the process because
they accumulated. This issue makes the code agree with that decision.

## What stays

`reconcile_worktrees`, `cleanup_worktree`, and the audit I/O — roughly a
350-line core — are genuinely used by `close_sprint`'s
`_prune_sprint_worktrees` and the `reconcile_worktrees` tool. The
accumulation-prevention sweeps must survive intact; that is the whole
reason they were built.

## Acceptance criteria

- [ ] The unreachable lifecycle functions are deleted (or archived to a
      branch if multi-worktree execution may return — the stakeholder
      decides which, but the docs get cut either way).
- [ ] The Parallel Path sections are removed from `execution.md`, and the
      sprint `worktree` frontmatter flag is removed or documented as
      inert. The spec must not re-orphan the code.
- [ ] `close-sprint`'s incorrect claim about `acquire_execution_lock`
      creating worktrees is corrected.
- [ ] `tests/clasi/test_worktree.py`'s lifecycle portions and
      `tests/system/test_worktree_and_planning_integration.py` are
      trimmed to match; reconcile/audit tests are kept.
- [ ] `worktree.py:351-360` uses `git worktree prune` rather than
      re-running `git worktree remove` on an already-deleted directory
      and ignoring the error.
- [ ] The full suite passes with the deletion in place, proving nothing
      live depended on the removed half.
