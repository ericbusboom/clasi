---
id: '003'
title: Add PreToolUse warning hook for Agent tool usage
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: agent-tool-warning-hook.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add PreToolUse warning hook for Agent tool usage

## Description

The team-lead has access to both the dispatch MCP tools (`dispatch_to_code_monkey`,
etc.) and Claude Code's built-in `Agent` tool. The dispatch tools guarantee
logging and contract validation. The `Agent` tool does not. The team-lead
consistently uses the `Agent` tool because it's the path of least resistance,
bypassing the dispatch infrastructure entirely.

Add a PreToolUse hook matching the `Agent` tool that prints a warning reminding
the user to use dispatch tools instead:

```
CLASI: You used the Agent tool instead of a dispatch_to_* MCP tool.
Dispatch tools provide logging and contract validation.
Use dispatch_to_* unless you have a specific reason not to.
```

The hook should NOT block — the `Agent` tool is legitimately needed for some
operations (e.g., explore agents, statusline-setup). It should only remind the
caller to prefer dispatch tools for work that should be logged.

The hook should be added to `.claude/settings.json` as a PreToolUse hook
targeting the `Agent` tool name.

## Acceptance Criteria

- [x] `.claude/settings.json` contains a PreToolUse hook matching the `Agent` tool
- [x] The hook prints the warning message to stderr or stdout
- [x] The hook does NOT block the `Agent` tool call (decision: allow)
- [x] The warning message mentions `dispatch_to_*` MCP tools
- [x] `uv run pytest` passes with no failures

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: None — this is a settings/hook configuration change
- **Verification command**: `uv run pytest`
