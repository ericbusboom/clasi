---
status: done
sprint: '010'
tickets:
- 010-001
---

# close-sprint skill missing ToolSearch step causes parameter drop

CLASI MCP tools are deferred — their schemas are not loaded at session start. Calling them without first fetching their schema via `ToolSearch` causes the harness to drop all parameters (arriving at the MCP server as `input_value={}`). The `close-sprint` skill does not include a `ToolSearch` step, so agents that follow it blindly call `close_sprint` with parameters that are silently dropped.

## Observed Failures

Two foreign repos hit this in the same session (2026-05-27):

- `/Volumes/Proj/proj/league-projects/infrastructure/inventory` — Sprint 002, all tickets done, AI hard-stopped with `sprint_id: Field required, input_value={}`
- `/Volumes/Proj/proj/league-projects/scratch/radio-robot` — Sprint 007, same error

Both `close_sprint` and `finalize_sprint` fail identically — the alias created in sprint 007 does not help because it is also a deferred tool subject to the same schema-loading requirement.

**Confirmed workaround:** in the clasi repo session (same day), `close_sprint` succeeded after `ToolSearch` loaded its schema first. This is the fix.

## Root Cause

The `close-sprint` skill (`clasi/plugin/skills/close-sprint/SKILL.md`) has no instruction to load the tool schema before calling it. Sprint 007 diagnosed this as a VS Code extension name-specific bug and created an alias, but the actual cause is the deferred-tool mechanism: any MCP tool called without a prior `ToolSearch` load will drop its parameters.

## Fix Required

1. Update `clasi/plugin/skills/close-sprint/SKILL.md` to call `ToolSearch` with `select:mcp__clasi__close_sprint` before invoking the tool.
2. Redistribute the updated skill to foreign repos via `clasr install` — the stale skill at `.claude/skills/close-sprint/SKILL.md` in each installed repo also needs to be updated.
3. Consider auditing other skills that call MCP tools to ensure they also load schemas first (execute-sprint, sprint-review, etc.).
