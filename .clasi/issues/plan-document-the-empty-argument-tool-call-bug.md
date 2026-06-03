---
status: pending
---

# Plan: Document the Empty-Argument Tool Call Bug

## Context

There is a confirmed bug in Claude Code (VS Code extension and possibly other harnesses) where **if any argument in a tool call is empty/null, all arguments to that tool are silently dropped** — the tool receives `input_value={}` regardless of what was passed. This caused repeated failures closing sprints (sprint 007, 010, 011) with the error `sprint_id: Field required, input_value={}`.

Sprint 010 diagnosed the proximate cause as deferred MCP tool schemas (ToolSearch required before calling), but the underlying harness behavior — dropping all args when any arg is empty — is a broader hazard that affects any tool call with optional parameters.

The user wants a **prominent, always-loaded rule** that:
1. Warns agents about this bug
2. Specifies the mitigation: use the string `"NONE"` as a sentinel for optional parameters that would otherwise be omitted/empty
3. Notes that the CLASI MCP server strips `"NONE"` before processing (see implementation note below)

## Scope

**What we are NOT doing:** Implementing the NONE-stripping logic in the MCP server (that's a separate code change). This plan is documentation/rules only — adding a prominent rule file that agents will always load.

**What we ARE doing:** Adding one new rule file in `.claude/rules/` with `paths: ["**"]` so it loads in every agent session for this project.

## Implementation

### New file: `.claude/rules/tool-call-empty-args.md`

```markdown
---
paths:
  - "**"
---

## CRITICAL: Empty Tool Arguments Drop ALL Parameters

There is a known bug in Claude Code where if **any** argument in a tool
call is empty or null, the harness silently drops **all** arguments and
the tool receives `input_value={}`. This caused repeated sprint-closure
failures (sprint 007, 010, 011) with errors like:
`sprint_id: Field required, input_value={}`.

### Rule

**Never make a tool call where any argument is empty/null when other
arguments are non-empty.**

### Mitigation for Optional Parameters

If a parameter is optional and you have nothing meaningful to pass:
- Use the sentinel string `"NONE"` instead of omitting it or passing `None`/`null`
- The CLASI MCP server strips `"NONE"` before dispatching, treating it as absent
- Example: `close_sprint(sprint_id="012", branch_name="NONE")` — not `close_sprint(sprint_id="012")`

**Only apply this to parameters that are truly optional** (documented as
nullable or optional). Required parameters must always have real values.

### Deferred MCP Tools Require ToolSearch First

CLASI MCP tools are deferred — their schemas are not loaded at session
start. Always call `ToolSearch` with `select:mcp__clasi__<tool_name>`
before calling any CLASI MCP tool for the first time in a session.
Skipping this step also causes the `input_value={}` symptom.
```

## Notes on NONE-stripping

**Confirmed: the MCP server does NOT yet strip `"NONE"`.** The `close_sprint` handler signature uses `Optional[str] = None` for optional params and passes them directly to FastMCP with no preprocessing. A `"NONE"` string would arrive as the literal string `"NONE"`, not as `None`.

Therefore the plan has two parts:
1. **Rule file** — documents the convention and the sentinel
2. **MCP server change** — adds preprocessing to strip `"NONE"` sentinel values from `Optional[str]` parameters before dispatching to tool functions

### MCP server implementation

In [clasi/mcp_server.py](clasi/mcp_server.py), in the `_logged_call_tool` wrapper (the existing logging wrapper around all tool calls), add a preprocessing step that strips `"NONE"` from any argument before passing it to the tool. This is the right place because it's a single central intercept point that covers ALL tools.

Alternatively: add a Pydantic `field_validator` in the tool signatures. But the central intercept is cleaner — one change covers everything.

The preprocessing rule: for each key/value in the arguments dict, if the value is the string `"NONE"`, replace it with `None`. This mirrors the intended behavior and doesn't affect parameters that genuinely use the string "NONE" as a value (an unlikely collision).

## Files to Create/Edit

| File | Action |
|------|--------|
| `.claude/rules/tool-call-empty-args.md` | **Create** — new always-loaded rule |
| `clasi/mcp_server.py` | **Edit** — add NONE-sentinel stripping in `_logged_call_tool` wrapper |

The team-lead `agent.md` already references the close-sprint skill which has its own ToolSearch step; the rule file is the right place for cross-cutting agent guidance.

## Verification

1. Read the new rule file to confirm it renders correctly.
2. Check that `paths: ["**"]` matches the pattern used by `mcp-required.md` (it does — confirmed).
3. Run `uv run pytest` to ensure the MCP server change doesn't break existing tests.
4. Manually verify sentinel stripping: call any CLASI MCP tool with an optional param set to `"NONE"` and confirm the server receives `None` (not the string `"NONE"`) — check MCP server logs.
