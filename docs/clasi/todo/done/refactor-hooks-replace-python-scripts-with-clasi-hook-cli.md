---
status: done
sprint: '004'
tickets:
- '001'
- '002'
- '003'
---

# Refactor hooks: replace Python scripts with `clasi hook` CLI calls

## Problem

The current hook setup in `.claude/hooks/` has Python scripts that are thin wrappers
calling back into CLASI code (e.g., `from clasi.hook_handlers import ...`). This is
problematic because:

1. **Python interpreter ambiguity** — `python3 .claude/hooks/foo.py` uses whatever
   `python3` is on PATH, not the CLASI package's interpreter. CLASI is installed via
   pipx, which bundles its own interpreter.
2. **Unnecessary indirection** — every hook script just imports and calls a CLASI
   function. The `clasi hook <event>` CLI subcommand already exists and does the same
   thing.
3. **`clasi init` skips hooks** — init currently reports "Unchanged: .claude/settings.json
   (hooks)" and doesn't update them, so users get stale hook configurations.

## Changes needed

### 1. Replace all Python hook scripts with `clasi hook` CLI calls

In `.claude/settings.json`, change every hook command from:
```
"command": "python3 .claude/hooks/subagent_start.py"
```
to:
```
"command": "clasi hook subagent-start"
```

Do this for all hooks: `subagent_start`, `subagent_stop`, `task_created`,
`task_completed`, `role_guard`, `mcp_guard`, `plan_to_todo`.

The `plan_to_todo.py` hook is a special case — it currently shells out to
`uv run clasi tool plan-to-todo` instead of using hook_handlers. Fold this
into the `clasi hook` subcommand as well.

The inline bash hook for git-commit version tagging should also become a
`clasi hook` subcommand.

### 2. Delete the Python hook scripts

Remove all `.py` files from `.claude/hooks/` once settings.json uses CLI calls.

### 3. Fix `clasi init` to update hooks in settings.json

The init command must write/overwrite the hooks section in `.claude/settings.json`
so that users get the correct hook configuration when they run `clasi init`.

### 4. Verify the `clasi hook` CLI subcommand handles all events

Confirm that `clasi hook <event>` in `clasi/cli.py` correctly dispatches to all
the handlers currently used by the Python scripts. Add any missing event mappings.
