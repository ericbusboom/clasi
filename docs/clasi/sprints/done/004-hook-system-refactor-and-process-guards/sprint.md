---
id: '004'
title: Hook System Refactor and Process Guards
status: done
branch: sprint/004-hook-system-refactor-and-process-guards
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
todos:
- refactor-hooks-replace-python-scripts-with-clasi-hook-cli.md
- exitplanmode-to-clasi-todo-integration.md
- role-guard-block-team-lead-source-writes.md
- execute-sprint-skill-move-tickets-to-done.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 004: Hook System Refactor and Process Guards

## Goals

1. Eliminate Python wrapper scripts in `.claude/hooks/` by replacing all hook
   commands with `clasi hook <event>` CLI calls.
2. Add the missing event dispatchers (`mcp-guard`, `plan-to-todo`,
   `commit-check`) to the `clasi hook` CLI and implement the `handle_hook()`
   dispatcher in `hook_handlers.py`.
3. Fix `clasi init` to write/overwrite the hooks section in `settings.json`
   on every run, so users always get the current hook configuration.
4. Tighten the role guard so that the team-lead session (tier 0) is
   structurally blocked from writing source code files.
5. Update the execute-sprint skill so that `move_ticket_to_done()` is called
   after each programmer task completes.

## Problem

The hook system has three intertwined problems:

**Interpreter ambiguity**: Hook commands invoke `python3 .claude/hooks/foo.py`,
but CLASI is installed via pipx with its own interpreter. On many systems the
ambient `python3` does not have `clasi` on its path, so the hook scripts fail
at import time.

**Unnecessary indirection**: Each `.py` hook script is a one-liner that imports
and calls a CLASI function. The `clasi hook <event>` CLI subcommand already
exists and is the correct mechanism, but is not wired up for all events and is
not used in practice.

**Stale configurations**: `clasi init` merges hooks into `settings.json` but
never overwrites existing entries. Users who installed CLASI before the
refactor never receive the updated hook commands.

Additionally, the role guard's tier detection works correctly but is missing a
coverage check: it allows writes inside `.claude/` broadly, which in theory
permits team-lead to overwrite source files that happen to sit under `.claude/`.
Investigation is needed to confirm the precise gap and tighten the guard.

Finally, the execute-sprint skill instructs programmers to set ticket
frontmatter to `done`, but does not call `move_ticket_to_done()`, leaving
tickets in the active `tickets/` directory instead of `tickets/done/`.

## Solution

**Hooks refactor (TODO 1 + TODO 2)**: Create a `handle_hook()` dispatcher in
`hook_handlers.py` that routes every event name to its handler. Add the three
missing CLI event names to the `click.Choice` list in `cli.py`. Update
`clasi/plugin/hooks/hooks.json` (the template) to use `clasi hook <event>`
commands. Update the live `.claude/settings.json` and delete the `.py` scripts.
Fix `clasi init` to always overwrite the hooks section when installing.

**Role guard fix (TODO 3)**: Read the actual guard logic in `hook_handlers.py`,
identify the exact gap, and tighten the allowed-path rules so tier-0 writes
to source files (`.py`, `.toml`, etc.) are blocked.

**Execute-sprint ticket move (TODO 4)**: Insert a step in
`clasi/plugin/skills/execute-sprint/SKILL.md` after each programmer task
completes that calls `move_ticket_to_done(ticket_path)`.

## Success Criteria

- `clasi hook subagent-start` (and all other events) executes without error
  when run from a CLASI-managed project.
- `clasi init` on an existing project overwrites hook commands in
  `settings.json`.
- `.claude/hooks/*.py` files are deleted from the live project and from
  `clasi/plugin/hooks/`.
- Team-lead attempting to Write a `.py` file receives a ROLE VIOLATION message.
- After a programmer completes a ticket during sprint execution, the ticket
  file is found in `tickets/done/`, not `tickets/`.
- All existing tests pass (`uv run pytest`).

## Scope

### In Scope

- `clasi/cli.py`: add missing event names to `clasi hook` CLI, wire
  `handle_hook()` dispatcher.
- `clasi/hook_handlers.py`: implement `handle_hook()` dispatcher, add
  handlers for `mcp-guard`, `plan-to-todo`, `commit-check`.
- `clasi/init_command.py`: overwrite hooks section unconditionally on init.
- `clasi/plugin/hooks/hooks.json`: update all commands to `clasi hook <event>`.
- `clasi/plugin/hooks/*.py`: delete all Python hook scripts from plugin template.
- `.claude/settings.json` (live): update hook commands to `clasi hook <event>`.
- `.claude/hooks/*.py` (live): delete all Python hook scripts.
- `clasi/plugin/skills/execute-sprint/SKILL.md`: add `move_ticket_to_done` step.
- `clasi/hook_handlers.py` `handle_role_guard`: tighten tier-0 write blocking.

### Out of Scope

- Changing what any hook handler actually does (logic stays the same).
- Adding new hook event types not already in use.
- Migrating the MCP server or state database.
- Changes to any test infrastructure beyond updating tests to cover new paths.

## Test Strategy

- Unit tests for `handle_hook()` dispatcher: verify each event name routes
  to the correct handler.
- Unit tests for the updated `handle_role_guard()`: verify that a tier-0
  attempt to write a `.py` file is blocked; verify `.claude/` writes still
  allowed.
- Unit tests for `clasi init`: verify that hooks are overwritten when the
  command is re-run on an existing `settings.json`.
- Smoke test: run `clasi hook subagent-start` with a minimal JSON payload on
  stdin and verify exit 0.
- All existing tests must continue to pass.

## Architecture Notes

- The `handle_hook()` dispatcher is the canonical entry point. `cli.py` calls
  it with the event name string; the dispatcher reads stdin and routes.
- The `plan_to_todo` event handler reuses `clasi.plan_to_todo.plan_to_todo()`
  unchanged — only the invocation path changes.
- The inline bash hook for git-commit version tagging becomes
  `clasi hook commit-check`.
- `clasi init` hook installation switches from merge-then-skip to
  overwrite-always so hook commands are always current.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Hook dispatcher and CLI wiring | — | 1 |
| 002 | Update settings.json and delete Python scripts | 001 | 2 |
| 003 | Fix clasi init to overwrite hooks | 001 | 2 |
| 004 | Tighten role guard for tier-0 source writes | — | 1 |
| 005 | Execute-sprint skill: move ticket to done | — | 1 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
