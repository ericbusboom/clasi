---
id: '002'
title: Update settings.json and delete Python hook scripts
status: done
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update settings.json and delete Python hook scripts

## Description

Once `handle_hook()` and the new CLI event names exist (ticket 001), the live
project configuration can be updated. This ticket:

1. Updates `.claude/settings.json` in the CLASI repo to replace all
   `python3 .claude/hooks/foo.py` commands with `clasi hook <event>`.
2. Replaces the inline bash commit-check PostToolUse hook with
   `clasi hook commit-check`.
3. Updates the ExitPlanMode PostToolUse entry from
   `python3 .claude/hooks/plan_to_todo.py` to `clasi hook plan-to-todo`.
4. Deletes all `.py` files from `.claude/hooks/`.

Both changes (settings.json update and script deletion) must be committed
atomically to avoid a window where scripts are gone but settings still
reference them.

## Acceptance Criteria

- [ ] `.claude/settings.json` contains no `python3` commands
- [ ] `.claude/settings.json` hook commands match the template in
  `clasi/plugin/hooks/hooks.json`
- [ ] `.claude/hooks/` directory contains no `.py` files
- [ ] `clasi hook subagent-start` executes successfully:
  `echo '{}' | clasi hook subagent-start` exits 0
- [ ] `clasi hook role-guard` executes successfully with a sample payload:
  `echo '{"file_path": ""}' | clasi hook role-guard` exits 0
- [ ] All existing tests pass (`uv run pytest`)

## Implementation Plan

### Approach

Edit `.claude/settings.json` to match the canonical content from
`clasi/plugin/hooks/hooks.json` after ticket 001's updates. Delete the seven
Python scripts. Both changes go in the same commit.

### Files to Modify

**`.claude/settings.json`** — replace the entire `hooks` block with:
```json
{
  "hooks": {
    "SubagentStart": [
      {"matcher": ".*", "hooks": [{"type": "command", "command": "clasi hook subagent-start"}]}
    ],
    "SubagentStop": [
      {"matcher": ".*", "hooks": [{"type": "command", "command": "clasi hook subagent-stop"}]}
    ],
    "TaskCreated": [
      {"matcher": ".*", "hooks": [{"type": "command", "command": "clasi hook task-created"}]}
    ],
    "TaskCompleted": [
      {"matcher": ".*", "hooks": [{"type": "command", "command": "clasi hook task-completed"}]}
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{"type": "command", "command": "clasi hook role-guard"}]
      },
      {
        "matcher": "mcp__clasi__create_ticket|mcp__clasi__create_sprint",
        "hooks": [{"type": "command", "command": "clasi hook mcp-guard"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "clasi hook commit-check"}]
      },
      {
        "matcher": "ExitPlanMode",
        "hooks": [{"type": "command", "command": "clasi hook plan-to-todo"}]
      }
    ]
  }
}
```

### Files to Delete

- `.claude/hooks/subagent_start.py`
- `.claude/hooks/subagent_stop.py`
- `.claude/hooks/task_created.py`
- `.claude/hooks/task_completed.py`
- `.claude/hooks/role_guard.py`
- `.claude/hooks/mcp_guard.py`
- `.claude/hooks/plan_to_todo.py`

### Testing Plan

- Smoke test: `echo '{}' | clasi hook subagent-start` exits 0.
- Smoke test: `echo '{"file_path": ""}' | clasi hook role-guard` exits 0.
- Verify no `.py` files remain: `ls .claude/hooks/` shows only non-Python
  files (or an empty directory).
- **Existing tests**: `uv run pytest` — all must pass.

### Documentation Updates

None. The `.claude/hooks/` directory may be left as an empty directory or
removed if git allows (a `.gitkeep` can be added if needed).
