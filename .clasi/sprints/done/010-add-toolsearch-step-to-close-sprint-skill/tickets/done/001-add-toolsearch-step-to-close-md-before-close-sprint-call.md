---
id: '001'
title: Add ToolSearch step to close.md before close_sprint call
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: close-sprint-skill-calls-wrong-tool.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add ToolSearch step to close.md before close_sprint call

## Description

CLASI MCP tools are deferred — their parameter schemas are not loaded at session
start. Any agent that calls a deferred tool without first fetching its schema via
`ToolSearch` will have all its parameters silently dropped by the harness, causing
a validation error such as `sprint_id: Field required, input_value={}`.

The `close-sprint` skill loads its instructions from
`clasi/schemas/se-process/instructions/close.md`. That file's current Process
section jumps directly to `close_sprint(...)` with no ToolSearch step, so every
agent following the skill hits the parameter-drop failure.

The fix is to insert a new numbered step in `close.md` immediately before the
`close_sprint` call block, instructing the agent to call `ToolSearch` with
`select:mcp__clasi__close_sprint`.

## Acceptance Criteria

- [x] `clasi/schemas/se-process/instructions/close.md` contains a step that calls
  `ToolSearch` with query `select:mcp__clasi__close_sprint` before the
  `close_sprint` invocation.
- [x] The new step includes a one-sentence explanation of why it is required
  (deferred-tool schema loading).
- [x] The existing Process steps are renumbered or the new step is inserted as a
  logically numbered sub-step so the sequence reads naturally.
- [x] No other content in `close.md` is changed.

## Implementation Plan

### Approach

Text insertion into a Markdown file. No code changes.

### File to Modify

- `clasi/schemas/se-process/instructions/close.md`

In the `## Process` section, before the current step 2 ("Call close_sprint"),
insert:

```
1.5. **Load the tool schema**: Call `ToolSearch` with query
   `select:mcp__clasi__close_sprint` to load the tool's parameter schema.
   This is required because CLASI MCP tools are deferred — calling them
   without first loading their schema causes all parameters to be silently
   dropped.
```

Alternatively, renumber the steps so the ToolSearch step is step 2 and the
existing step 2 becomes step 3. Either presentation is acceptable; the important
thing is that the ToolSearch step appears before the `close_sprint` call.

### Testing Plan

1. Read the updated `close.md` and verify the ToolSearch step is present before
   the `close_sprint` call block.
2. Run `uv run pytest` to confirm no existing tests are broken (no test touches
   this file, so the run should be clean).

### Documentation Updates

None required beyond the file change itself. The issue
`close-sprint-skill-calls-wrong-tool.md` will be archived when this ticket is
moved to done.
