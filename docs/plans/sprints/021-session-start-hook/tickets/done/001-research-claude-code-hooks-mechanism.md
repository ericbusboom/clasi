---
id: "001"
title: "Research Claude Code hooks mechanism"
status: done
use-cases: [SUC-001]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Research Claude Code hooks mechanism

## Description

Before building the session-start hook, we need to understand the exact
mechanism available in the current version of Claude Code. This is a
research ticket — the output is knowledge, not code.

Tasks:

1. **Read Claude Code documentation** — Determine how hooks are
   configured (e.g., `.claude/settings.local.json`, a dedicated
   `.claude/hooks/` directory, or another mechanism).
2. **Review Superpowers `session-start.sh`** — Examine how the
   Superpowers project implements its session-start hook. Note the
   format, trigger point, and how output is surfaced to the agent.
3. **Determine the correct format** — Document which hook type to use,
   what file(s) to create, and how the hook output reaches the agent
   context.
4. **Write findings** — Record the decision in a ticket plan file or
   notes section so ticket 002 can implement without guessing.

This ticket produces no code changes. It de-risks ticket 002 by
resolving unknowns up front.

## Research Findings

### Hook Mechanism

Claude Code hooks are configured in `.claude/settings.local.json` under
a `hooks` key. The format is:

```json
{
  "hooks": {
    "PreToolUse": [...],
    "PostToolUse": [...],
    "Notification": [...],
    "Stop": [...],
    "UserPromptSubmit": [...]
  }
}
```

Each hook event maps to an array of hook entries. Each entry specifies a
`type` (e.g., `"command"`), a `command` string (bash command to run), and
an optional `timeout` in milliseconds.

### Recommended Approach

Use the `UserPromptSubmit` hook event. This fires when the user submits
a prompt — the closest to "session start" available. The hook command
echoes a reminder to load the SE process.

Hook entry format:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": "echo 'CLASI: Call get_se_overview() to load the SE process before doing any work.'"
      }
    ]
  }
}
```

### Superpowers Review

The Superpowers project uses a similar pattern — a bash command that
outputs a reminder message. The output is surfaced to the agent as
context before it processes the user's prompt.

### Decision for Ticket 002

- **Where**: `.claude/settings.local.json` (already managed by init)
- **Format**: JSON `hooks.UserPromptSubmit` array entry
- **Content**: Echo command with CLASI loading reminder
- **Integration**: Extend `_update_settings_json()` in `init_command.py`
  to also install the hook configuration, preserving existing settings
- **Idempotency**: Check if hook already exists before adding

## Acceptance Criteria

- [x] Hook mechanism is documented (where hooks live, how they are configured)
- [x] Correct format for a session-start hook is confirmed (file format, trigger type, output handling)
- [x] Superpowers `session-start.sh` approach has been reviewed and findings recorded
- [x] Decision doc or notes exist (in ticket plan or sprint notes) for ticket 002 to reference

## Testing

- **Existing tests to run**: `uv run pytest` (no regressions — no code changes expected)
- **New tests to write**: None (research ticket; no code modified)
- **Verification command**: `uv run pytest`
