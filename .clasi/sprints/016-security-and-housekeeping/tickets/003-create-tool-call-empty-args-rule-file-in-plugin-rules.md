---
id: '003'
title: Create tool-call-empty-args rule file in plugin/rules
status: open
use-cases:
- SUC-016-005
depends-on:
- '002'
github-issue: ''
issue: plan-document-the-empty-argument-tool-call-bug.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create tool-call-empty-args rule file in plugin/rules

## Description

There is no always-loaded rule file documenting the confirmed Claude Code harness bug
(empty/null arg → all args dropped → tool sees `input_value={}`) or the `"NONE"` sentinel
mitigation. Agents rediscover this failure mode repeatedly, causing sprint-closure failures
(sprints 007, 010, 011).

This ticket creates `clasi/plugin/rules/tool-call-empty-args.md` with `paths: ["**"]`
frontmatter so it loads in every agent session. It also must document the server-side
stripping (completed in ticket 002) so agents understand the full round-trip.

Depends on ticket 002 because the rule must accurately describe the extraction of
`_strip_none_sentinel` as an explicitly testable function.

## Acceptance Criteria

- [ ] `clasi/plugin/rules/tool-call-empty-args.md` exists.
- [ ] Frontmatter contains `paths: ["**"]` so the file loads in all sessions.
- [ ] File documents the confirmed bug: empty or null argument in a tool call causes all arguments to be silently dropped; the tool receives `input_value={}`.
- [ ] File documents the mitigation: pass `"NONE"` (literal string) for any optional parameter instead of empty/null.
- [ ] File documents server-side stripping: `_strip_none_sentinel` in `clasi/mcp_server.py` converts `"NONE"` to `None` before dispatch, so tool functions receive `None` and apply their defaults.
- [ ] File documents the ToolSearch-first requirement: deferred MCP tools must have their schema fetched via `ToolSearch` before they can be called.
- [ ] `clasi init` installs this file into `.claude/rules/` in the target project (verify that the Claude platform installer already copies all `plugin/rules/*.md` files; no installer code change needed if so).
- [ ] `uv run pytest` is green (no new test required for this ticket, but existing tests must pass — including the content smoke test if one covers `plugin/rules/`).

## Implementation Plan

### Approach

Create a single markdown file. The Claude platform installer already copies everything in
`plugin/rules/` into the target project's `.claude/rules/`; verify this in
`clasi/platforms/claude.py` before finalizing.

### Files to Create

- `clasi/plugin/rules/tool-call-empty-args.md`

### File content outline

```markdown
---
paths: ["**"]
---

# Tool Call Empty-Argument Bug

## The Bug

Confirmed in Claude Code (VS Code extension and CLI harness): if **any** argument in
a tool call is empty (`""`) or null (`None`/omitted), the harness silently drops **all**
arguments. The tool receives `input_value={}` — a completely empty input — and Pydantic
validation raises `Field required` for any required fields.

Symptoms observed: sprint-closure failures with `sprint_id: Field required, input_value={}`.

## Mitigation: Use "NONE" for optional parameters

When a parameter is optional and you have no value to pass, use the literal string
`"NONE"` instead of empty string or null:

  CORRECT:   close_sprint(sprint_id="016", test_command="NONE")
  INCORRECT: close_sprint(sprint_id="016", test_command="")
  INCORRECT: close_sprint(sprint_id="016")   # if tool call omits optional args as null

## Server-side stripping

The CLASI MCP server converts `"NONE"` back to `None` before dispatching to the tool
function. The `_strip_none_sentinel` function in `clasi/mcp_server.py` handles this
transparently. Tool implementations receive `None` and apply their defaults normally.

Do NOT pass `"NONE"` for required parameters — only for optional ones.

## ToolSearch first for deferred tools

MCP tools listed as "deferred" in system-reminder messages have no loaded schema.
Calling them directly will fail with `InputValidationError`. Always call `ToolSearch`
with `query: "select:<ToolName>"` to load the schema before the first invocation.
```

### Files to Verify (no change expected)

- `clasi/platforms/claude.py` — confirm `plugin/rules/` files are copied to
  `.claude/rules/` during `clasi init`. If not, add the copy step.

### Testing Plan

Check whether `tests/system/test_content_smoke.py` or `tests/unit/test_mcp_server.py`
already verify that `plugin/rules/` files exist. If `TestContentPath.test_resolves_rules_directory`
is the only check, add a targeted test:

```python
def test_tool_call_empty_args_rule_exists(self):
    rule = content_path("plugin", "rules", "tool-call-empty-args.md")
    assert rule.is_file()
    content = rule.read_text(encoding="utf-8")
    assert 'paths: ["**"]' in content
    assert "NONE" in content
```

Add this to `TestContentPath` in `tests/unit/test_mcp_server.py`.

### Documentation Updates

The rule file itself is the documentation artifact. No additional docs needed.
