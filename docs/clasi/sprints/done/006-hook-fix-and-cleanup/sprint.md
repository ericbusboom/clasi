---
id: '006'
title: Hook Fix and Cleanup
status: done
branch: sprint/006-hook-fix-and-cleanup
use-cases:
- SUC-001
- SUC-002
todos:
- fix-plan-to-todo-hook-agent-ignores-do-not-implement-instruction.md
- plan-rebase-sprint-branch-before-merge-on-close.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 006: Hook Fix and Cleanup

## Goals

1. Fix the `plan-to-todo` PostToolUse hook so the model actually sees the stop instruction after saving a plan as a TODO.
2. Use `planFilePath` from the hook payload to target the exact plan file instead of the mtime heuristic.
3. Mark the rebase-before-merge TODO as done -- that work was completed in Sprint 005.

## Problem

The `handle_plan_to_todo` PostToolUse hook fires after `ExitPlanMode`, saves the plan as a TODO, and then prints a "Do NOT implement" message to stdout with `sys.exit(0)`. Claude Code only surfaces PostToolUse hook output to the model when the hook writes to **stderr** and exits with code **2**. With stdout + exit 0, the stop message goes to the debug log only and the model never sees it -- so it proceeds to implement the plan immediately after saving it.

A separate issue: the hook currently picks the newest file in `~/.claude/plans/` by mtime. The hook payload already contains the exact path at `tool_input.planFilePath`. Using the payload path is more reliable and eliminates the race condition with other projects.

The rebase TODO (`plan-rebase-sprint-branch-before-merge-on-close.md`) was fully implemented in Sprint 005 but the TODO file was never moved to done. This sprint closes that gap.

## Solution

1. **Fix hook output**: In `handle_plan_to_todo()`, extract `planFilePath` from the payload, pass it to `plan_to_todo()`, and write the stop message as a JSON block to stderr with exit code 2 when a TODO was created.
2. **Add `plan_file` parameter to `plan_to_todo()`**: Accept an optional `plan_file: Optional[Path]` and use it directly when provided; fall back to the mtime heuristic when absent.
3. **Close the rebase TODO**: Move `plan-rebase-sprint-branch-before-merge-on-close.md` to done -- no new code required.

## Success Criteria

- After `ExitPlanMode`, the agent sees a `decision: block` message in hook feedback and stops without implementing.
- `plan_to_todo()` uses the payload-supplied path when available, verified by test.
- `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v` passes.
- The rebase TODO is in `done/` status.

## Scope

### In Scope

- `clasi/hook_handlers.py` -- extract `planFilePath`, pass to `plan_to_todo`, change print to stderr JSON + exit 2
- `clasi/plan_to_todo.py` -- add `plan_file: Optional[Path]` parameter, use it when provided
- `tests/unit/test_hook_handlers.py` -- update exit code assertions and output assertions
- `tests/unit/test_plan_to_todo.py` -- add tests for `plan_file` parameter path
- Move `plan-rebase-sprint-branch-before-merge-on-close.md` TODO to done

### Out of Scope

- Any changes to `sprint.py`, `artifact_tools.py`, or the git workflow (done in Sprint 005)
- Debug payload appending behavior (introduced in Sprint 005, kept as-is)
- Removing the debug block from `plan_to_todo()` (deferred until debug data is no longer needed)
- MCP server, state DB, or other sprint lifecycle changes

## Test Strategy

- Unit tests for `handle_plan_to_todo`: verify exit code 2 when a TODO is created, stderr contains JSON with `decision: block`, stdout is empty, and `planFilePath` from payload is passed as `plan_file` argument.
- Unit tests for `plan_to_todo`: verify that when `plan_file` is provided, that specific file is used (not the mtime-newest file), and the provided file is deleted after conversion.
- Existing tests for the no-plan-file path (exit 0, no output) must continue to pass.

## Architecture Notes

The change is narrow: two functions in two modules gain one additional parameter each. No new modules, no new dependencies. The fallback to mtime heuristic preserves backward compatibility for any caller that does not have a payload path available.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Add plan_file parameter to plan_to_todo() | — | 1 |
| 002 | Fix hook output: stderr + exit 2, extract planFilePath | 001 | 2 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
