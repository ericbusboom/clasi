---
id: '001'
title: Hook dispatcher and CLI wiring
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo:
- refactor-hooks-replace-python-scripts-with-clasi-hook-cli.md
- exitplanmode-to-clasi-todo-integration.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Hook dispatcher and CLI wiring

## Description

The `clasi hook <event>` CLI command exists in `cli.py` but calls
`handle_hook(event)` which does not yet exist in `hook_handlers.py`. The CLI
also only accepts five event names, missing `mcp-guard`, `plan-to-todo`, and
`commit-check`.

This ticket:
1. Implements `handle_hook(event: str) -> None` in `hook_handlers.py` as the
   central dispatcher that reads stdin JSON and routes to the correct handler.
2. Adds `handle_plan_to_todo()` handler that wraps `clasi.plan_to_todo.plan_to_todo()`.
3. Adds `handle_commit_check()` handler that replaces the inline bash PostToolUse
   hook (checks if the git commit was on master and prints the version bump reminder).
4. Extends the `click.Choice` list in `cli.py` with `mcp-guard`, `plan-to-todo`,
   `commit-check`.
5. Updates `clasi/plugin/hooks/hooks.json` to use `clasi hook <event>` for all
   entries, and adds the missing ExitPlanMode PostToolUse entry.
6. Removes all Python hook scripts from `clasi/plugin/hooks/` (the template
   directory — the live `.claude/hooks/` scripts are handled in ticket 002).

## Acceptance Criteria

- [x] `clasi/hook_handlers.py` exports `handle_hook(event: str) -> None`
- [x] `handle_hook` routes each of the 8 event names to the correct handler:
  `role-guard`, `subagent-start`, `subagent-stop`, `task-created`,
  `task-completed`, `mcp-guard`, `plan-to-todo`, `commit-check`
- [x] `handle_hook` calls `sys.exit(1)` with an error message for unknown events
- [x] `handle_plan_to_todo()` exists and delegates to `clasi.plan_to_todo.plan_to_todo()`
- [x] `handle_commit_check()` exists and prints a version bump reminder when
  a git commit on master/main is detected (reads `TOOL_INPUT` from env)
- [x] `cli.py` `click.Choice` includes all 8 event names
- [x] `clasi/plugin/hooks/hooks.json` uses `clasi hook <event>` for all commands
- [x] `clasi/plugin/hooks/hooks.json` includes ExitPlanMode PostToolUse entry
  pointing to `clasi hook plan-to-todo`
- [x] All `*.py` files removed from `clasi/plugin/hooks/`

## Implementation Plan

### Approach

Add `handle_hook()` to `hook_handlers.py` as a pure routing function. Keep all
handler logic in the existing handler functions. Add two new thin handlers
(`handle_plan_to_todo`, `handle_commit_check`). Extend `cli.py` with the three
missing choice names. Update the hooks.json template and delete plugin .py files.

### Files to Modify

**`clasi/hook_handlers.py`**:
- Add `handle_plan_to_todo(payload: dict) -> None`: reads payload (not needed),
  calls `from clasi.plan_to_todo import plan_to_todo`, invokes
  `plan_to_todo(Path.home() / ".claude" / "plans", Path("docs/clasi/todo"))`,
  prints result if any, exits 0.
- Add `handle_commit_check(payload: dict) -> None`: reads `TOOL_INPUT` from
  `os.environ`. If it contains `git commit` and the current git branch is
  `master` or `main`, prints
  `"CLASI: You committed on master. Call tag_version() to bump the version."`
  Exits 0 in all cases.
- Add `handle_hook(event: str) -> None`: calls `read_payload()`, builds a
  dispatch dict `{event_name: handler_fn}`, looks up and calls the handler,
  or exits 1 for unknown events.

**`clasi/cli.py`**:
- Extend `click.Choice` with `"mcp-guard"`, `"plan-to-todo"`, `"commit-check"`.

**`clasi/plugin/hooks/hooks.json`**:
- Replace every `python3 .claude/hooks/foo.py` command with the appropriate
  `clasi hook <event>` string.
- Replace the inline bash commit-check string with `"clasi hook commit-check"`.
- Add ExitPlanMode PostToolUse entry with `"clasi hook plan-to-todo"`.

### Files to Delete

- `clasi/plugin/hooks/subagent_start.py`
- `clasi/plugin/hooks/subagent_stop.py`
- `clasi/plugin/hooks/task_created.py`
- `clasi/plugin/hooks/task_completed.py`
- `clasi/plugin/hooks/role_guard.py`
- `clasi/plugin/hooks/mcp_guard.py`

(`.claude/hooks/plan_to_todo.py` is only in the live project, not in the plugin
template — delete it in ticket 002.)

### Testing Plan

- **New tests** in `tests/test_hook_handlers.py` (or `tests/test_handle_hook.py`):
  - Test each event name routes to the correct handler (mock handlers, verify call).
  - Test unknown event causes `SystemExit(1)`.
  - Test `handle_commit_check` with `TOOL_INPUT` containing `git commit` on master
    prints the reminder; without `git commit` exits silently.
  - Test `handle_plan_to_todo` calls `plan_to_todo()`.
- **Existing tests**: `uv run pytest` — all must pass.

### Documentation Updates

None beyond code changes. The hooks.json template is self-documenting.
