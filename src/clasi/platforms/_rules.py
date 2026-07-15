"""Canonical rule body content for all five CLASI path-scoped rules.

This module is the single source of truth for rule content.  Both
``claude.py`` and ``codex.py`` import from it.  Neither platform
hardcodes rule strings of its own.

Boundary: data-only module.  No I/O, no side effects, no imports from
other CLASI modules.  Leaf node in the dependency graph.
"""

# ---------------------------------------------------------------------------
# Rule bodies (prose text only — no YAML frontmatter, no platform wrapper)
# ---------------------------------------------------------------------------

MCP_REQUIRED_BODY = """\
This project uses the CLASI MCP server. Before doing ANY work:

1. **Check for the OOP override first.** If the file `.clasi/oop`
   exists in the project root, ignore CLASI entirely for this session:
   skip MCP verification, skip all CLASI process gates (sprints,
   tickets, TODOs, artifact rules), and proceed with the user's
   request as you would in any non-CLASI repo. Do not call
   `get_version()` or any other CLASI MCP tool. The stakeholder has
   explicitly opted out for this checkout.
2. Otherwise, call `get_version()` to verify the MCP server is running.
3. If the call fails, STOP. Do not proceed. Tell the stakeholder:
   "The CLASI MCP server is not available. Check .mcp.json and
   restart the session, or create `.clasi/oop` to bypass CLASI
   for this session."
4. Do NOT create sprint directories, tickets, TODOs, or planning
   artifacts manually. Do NOT improvise workarounds. All SE process
   operations require the MCP server.
"""

CLASI_ARTIFACTS_BODY = """\
You are modifying CLASI planning artifacts. Before making changes:

1. If `.clasi/oop` exists, the stakeholder has opted out of CLASI
   for this session. Skip these gates entirely and proceed.
2. Confirm you have an active sprint (`list_sprints(status="active")`),
   or the stakeholder said "out of process" / "direct change".
3. If creating or modifying tickets, the sprint must be in `ticketing`
   or `executing` phase (`get_sprint_phase(sprint_id)`).
4. Use CLASI MCP tools for all artifact operations — do not create
   sprint/ticket/TODO files manually.

Direct edits to `clasi/sprints/` are blocked for team-lead. Use MCP tools.
"""

SOURCE_CODE_BODY = """\
You are modifying source code or tests. This rule applies everywhere
except CLASI's own process artifacts and docs — `.clasi/`, `.claude/`,
`docs/`, and `*.md` files are not source code and are not gated by this
rule (no glob can express "everything except these four," so this
exclusion lives here in prose instead of in `paths:`).

Before writing code:

1. If `.clasi/oop` exists, the stakeholder has opted out of CLASI
   for this session. Skip these gates entirely and proceed.
2. You must have a ticket in `in-progress` status, or the stakeholder
   said "out of process".
3. If you have a ticket, follow the execute-ticket skill — call
   `get_skill_definition("execute-ticket")` if unsure of the steps.
4. Run the project's test suite after changes.
5. A commit message is not a process action. Only an MCP call (e.g.
   `update_ticket_status`, `move_ticket_to_done`) moves a ticket —
   writing "closes 005" or similar in a commit message does not.
"""

TODO_DIR_BODY = """\
Use the CLASI `issue` skill or `move_issue_to_done` MCP tool for issue
operations. Do not use the generic TodoWrite tool for CLASI issues.

Exception: if `.clasi/oop` exists, the stakeholder has opted out
of CLASI for this session. Use whatever TODO mechanism you prefer.
"""

GIT_COMMITS_BODY = """\
Before committing, verify:
1. All tests pass (run the project's test suite).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.

After committing substantive changes, run `dotconfig version bump` to
advance the version, then commit that change (`chore: bump version`).
Tools are installed editable, so the version is how sessions tell
which code is live — bump per commit, not just at sprint close.
Skip the manual bump right before `close_sprint` (it bumps + tags).

See `instructions/git-workflow` for full rules.
"""

TOOL_CALL_EMPTY_ARGS_BODY = """\
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

Note: a parameter that legitimately accepts the string `"NONE"` as a real value would
be incorrectly stripped. This is a known limitation of the blanket-sentinel approach.

## ToolSearch first for deferred tools

MCP tools listed as "deferred" in system-reminder messages have no loaded schema.
Calling them directly will fail with `InputValidationError`. Always call `ToolSearch`
with `query: "select:<ToolName>"` to load the schema before the first invocation.
"""
