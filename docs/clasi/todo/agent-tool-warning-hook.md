---
status: pending
---

# Add PreToolUse Warning Hook for Agent Tool Usage

## Problem

The team-lead has access to both the dispatch MCP tools
(dispatch_to_code_monkey, etc.) and Claude Code's built-in Agent tool.
The dispatch tools guarantee logging and contract validation. The Agent
tool does not. The team-lead consistently uses the Agent tool because
it's the path of least resistance, bypassing the dispatch infrastructure
entirely.

## Proposed Fix

Add a PreToolUse hook matching the `Agent` tool that prints a warning:

```
CLASI: You used the Agent tool instead of a dispatch_to_* MCP tool.
Dispatch tools provide logging and contract validation.
Use dispatch_to_* unless you have a specific reason not to.
```

The hook should NOT block — the Agent tool is legitimately needed for
some operations. It should remind the team-lead to use dispatch tools
for work that should be logged.
