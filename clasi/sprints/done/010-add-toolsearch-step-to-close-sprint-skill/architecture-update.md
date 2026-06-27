---
sprint: "010"
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update -- Sprint 010: Add ToolSearch step to close-sprint skill

## What Changed

`clasi/schemas/se-process/instructions/close.md` gains one new numbered step
between the existing "Confirm with stakeholder" step and the "Call close_sprint"
step. The new step instructs the executing agent to call `ToolSearch` with
`select:mcp__clasi__close_sprint` before invoking the tool.

No source modules, data models, MCP tool implementations, or other skill files
are changed in this sprint.

## Why

SUC-001 requires that an agent following the close-sprint skill can successfully
pass parameters to `close_sprint`. CLASI MCP tools are deferred — the harness
does not load their schemas at session start. Calling a deferred tool without
first fetching its schema via `ToolSearch` causes the harness to silently drop
all parameters, resulting in a `sprint_id: Field required, input_value={}` error.

The fix is localized to the skill instruction file, which is the authoritative
document an agent reads when executing the close-sprint workflow.

## Impact on Existing Components

None. `close.md` is a static instruction document with no runtime role in the
MCP server, CLI, or plugin system. Adding a step to it does not change any
interface, module boundary, or dependency.

## Migration Concerns

None. The change is purely additive. Agents following the old skill that already
happen to call `ToolSearch` before `close_sprint` (for any reason) are
unaffected. Foreign repos using an older installed copy of the skill will
continue to fail until the user redistributes the updated file via `clasr
install` — this is expected and documented in the issue.
