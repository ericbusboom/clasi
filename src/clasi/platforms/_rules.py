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

1. **Check for the OOP override first.** If `clasi oop status` (or the
   presence of the emergency file `.clasi/oop`) shows the bypass active,
   ignore CLASI entirely for this session: skip MCP verification, skip
   all CLASI process gates (sprints, tickets, TODOs, artifact rules), and
   proceed with the user's request as you would in any non-CLASI repo.
   Do not call `get_version()` or any other CLASI MCP tool. The
   stakeholder has explicitly opted out for this checkout via
   `clasi oop on --reason '...'`.
2. Otherwise, call `get_version()` to verify the MCP server is running.
3. If the call fails, STOP. Do not proceed. Tell the stakeholder:
   "The CLASI MCP server is not available. Check .mcp.json and
   restart the session, or run `clasi oop on --reason '...'` to bypass
   CLASI for this session (or create `.clasi/oop` as an emergency
   fallback if `clasi` itself is broken)."
4. Do NOT create sprint directories, tickets, TODOs, or planning
   artifacts manually. Do NOT improvise workarounds. All SE process
   operations require the MCP server.
"""

CLASI_ARTIFACTS_BODY = """\
You are modifying CLASI planning artifacts. Before making changes:

1. If the OOP bypass is active (`clasi oop status`; enabled via
   `clasi oop on --reason '...'`, or the emergency file `.clasi/oop`),
   the stakeholder has opted out of CLASI for this session. Skip these
   gates entirely and proceed.
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

1. If the OOP bypass is active (`clasi oop status`; enabled via
   `clasi oop on --reason '...'`, or the emergency file `.clasi/oop`),
   the stakeholder has opted out of CLASI for this session. Skip these
   gates entirely and proceed.
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

Exception: if the OOP bypass is active (`clasi oop status`; enabled via
`clasi oop on --reason '...'`, or the emergency file `.clasi/oop`), the
stakeholder has opted out of CLASI for this session. Use whatever TODO
mechanism you prefer.
"""

GIT_COMMITS_BODY = """\
Before committing, verify:
1. All tests pass (run the project's test suite).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.

## Version bump cadence

Cadence: **once per sprint, at `close_sprint`. Do not run
`dotconfig version bump` manually during ticket work on a sprint
branch** — `close_sprint` already bumps and tags exactly once per
sprint (`version_trigger` setting, default `every_change`, evaluated
at sprint close). A manual mid-sprint bump would double-count against
that, not add signal.

Tools are installed editable, so "which code is live" still needs an
answer between commits — that need hasn't gone away, it's now met by
an automatic check instead of a manual one. CLASI's own staleness
detection (`clasi.staleness.check_staleness`, wired into `get_version()`
and the role/mcp guards) compares the running build against this
project's source on effectively every hook call and fails closed
(`stale-guard`) on drift. That fires far more often, and more reliably,
than an agent remembering to bump after each commit — bumping is a
release-note-style marker of "a sprint finished," not the live-build
check anymore.

**Exception — OOP / non-sprint commits**: if working directly on
`master` (no sprint branch), there is no `close_sprint` event to anchor
to. Run `dotconfig version bump` after each OOP commit and commit the
result (`chore: bump version`), same as before.

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
