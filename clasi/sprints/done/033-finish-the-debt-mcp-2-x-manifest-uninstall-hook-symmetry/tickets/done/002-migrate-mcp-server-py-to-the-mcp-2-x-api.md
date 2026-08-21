---
id: '002'
title: Migrate mcp_server.py to the mcp 2.x API
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: migrate-to-mcp-2-x-api.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Migrate mcp_server.py to the mcp 2.x API

## Description

**Read this whole ticket, including Process Notes, before writing any
code.** This is the highest-hazard ticket in the reliability campaign:
CLASI's own MCP server is the tooling the team-lead uses to run this
sprint. If this migration lands broken, `clasi mcp` fails to start and
every MCP tool (`create_ticket`, `update_ticket_status`,
`move_ticket_to_done`, `close_sprint`, ...) becomes unavailable — there
is no fallback to "the old code still runs," because the old code and
the new code cannot both be correct against the same installed `mcp`
version at once.

`src/clasi/mcp_server.py` imports `from mcp.server.fastmcp import
FastMCP`, an API surface `mcp` 2.x deletes entirely.
`pyproject.toml` currently caps `mcp>=1.0,<2.0` (sprint 029 ticket 001)
specifically to neutralize this. This ticket's precondition — the owned
`@clasi_tool` decorator in `src/clasi/tools/_common.py` (sprint 030
ticket 005) — is **verified, not assumed**, to already be fully
decoupled from FastMCP: `_common.py` has zero imports of `mcp`,
`FastMCP`, or `MCPServer` anywhere in the file. Do not re-verify this
from scratch; it was confirmed by grep during sprint planning and is
recorded in `clasi/sprints/033-.../design/tools-DESIGN.md`'s sprint-033
entry.

The actual `mcp` 2.x API surface was verified during planning by
installing `mcp==2.0.0` (currently the only 2.x release) into a
disposable scratch venv and inspecting it directly — do not re-derive
this from the issue text's "or whatever the 2.x equivalent is by the
time this is picked up." What was found:

- `FastMCP` is renamed `MCPServer`, at `mcp.server.mcpserver.MCPServer`
  (not `mcp.server.fastmcp`). Constructor keeps the `(name, ...,
  instructions=...)` shape `mcp_server.py:42-49` already uses; `.tool()`
  and `.run(transport="stdio")` are both present with the same call
  shape already in use at `mcp_server.py:236`.
- `mcp_server.py:149`'s `self.server._mcp_server.instructions = ...`
  (staleness-warning append) breaks — `_mcp_server` doesn't exist under
  2.x. Its 2.x equivalent is `self.server._lowlevel_server.instructions`
  (a plain settable attribute, not a read-only property — `MCPServer`'s
  own `instructions` property is read-only, `return
  self._lowlevel_server.instructions`). This call site is already
  wrapped in `try/except AttributeError` (`mcp_server.py:148-156`), so
  under 1.x-vs-2.x confusion it degrades to a logged warning rather than
  crashing — fix the attribute name anyway; do not rely on the guard as
  a substitute for the fix.
- `mcp_server.py:184` and `:191-192`'s `self.server._tool_manager._tools`
  (diagnostic tool-count/schema dump at startup) is confirmed
  structurally unchanged under 2.x — `mcp.server.mcpserver.tools.
  tool_manager.ToolManager._tools` is still a plain `dict[str, Tool]` at
  the same attribute path off `self._tool_manager`. This is the **one**
  of the four private-internal touches with **no** exception guard today
  — wrap it (see Acceptance Criteria) so a *future* private-shape change
  degrades to a missing log line instead of crashing server startup.
- `mcp_server.py:214-232`'s `mcp.types.JSONRPCMessage.model_validate_json`
  monkey-patch (raw-RPC diagnostic tap, flagged in `tools-DESIGN.md` as
  permanent debug scaffolding since sprint 030) is confirmed to still
  resolve under 2.x — `mcp.types.JSONRPCMessage` mirrors the standalone
  `mcp_types.JSONRPCMessage` package, a pydantic `RootModel` that still
  exposes `model_validate_json`. Already guarded by a broad `try/except`.
  **Leave this exactly as it is** — verify it still installs without
  raising, do not refactor or remove it; its cleanup is explicitly out of
  this ticket's scope (see sprint.md Out of Scope).

See `clasi/sprints/033-.../sprint.md` Architecture §4 (diagram) and §5
("What Changed — ticket 002") for the full write-up, and §"Migration
Concerns" for the sequencing and rollback plan below, which this ticket
must follow exactly.

## Acceptance Criteria

- [x] `mcp_server.py`'s `from mcp.server.fastmcp import FastMCP` becomes
      `from mcp.server.mcpserver import MCPServer`; `FastMCP(...)`
      becomes `MCPServer(...)` at the one construction site
      (`mcp_server.py:42`); every other reference to the type name in
      this file and its tests is updated to match.
- [x] `self.server._mcp_server.instructions` becomes
      `self.server._lowlevel_server.instructions`
      (`mcp_server.py:149`); the surrounding `try/except AttributeError`
      is unchanged.
- [x] `self.server._tool_manager._tools` (`mcp_server.py:184`, `:191-192`)
      is wrapped so a missing/renamed attribute logs a warning and skips
      the diagnostic dump instead of raising — matching the existing
      guard pattern the instructions-write already uses, not a bespoke
      new pattern.
- [x] The `JSONRPCMessage.model_validate_json` tap
      (`mcp_server.py:214-232`) is verified to install without raising
      under `mcp==2.0.0` (its existing `try/except Exception` already
      logs and continues on failure either way) — no code change to this
      block beyond what's needed for it to still be reached.
      **Correction to the planner's verified-API-surface claim, found
      during this ticket's own re-verification**: under the real
      `mcp==2.0.0`, `mcp.types.JSONRPCMessage` is `typing.Union[
      JSONRPCRequest, JSONRPCNotification, JSONRPCResponse,
      JSONRPCError]` (a plain `Union`/`UnionType`, not a pydantic
      `RootModel`), so `_mt.JSONRPCMessage.model_validate_json` raises
      `AttributeError` immediately. The tap does **not** "still resolve"
      as the planner's API-surface note claimed. It does, however,
      satisfy this criterion exactly as worded: the surrounding
      `try/except Exception` catches the `AttributeError`, logs
      `"raw-rpc tap: failed to install (...)"` at WARNING, and execution
      continues — confirmed live in three separate runs (disposable
      scratch venv, this project's own synced `.venv`, and the
      fresh-resolve Docker container), no traceback in any of them. Left
      untouched per this ticket's explicit instruction not to refactor
      it; flagging the corrected fact here since "verified unchanged" is
      a claim someone should be able to check later, and the tap is now
      silently a no-op rather than an active diagnostic — worth knowing
      for whoever eventually does the deferred debug-scaffolding
      cleanup.
- [x] `tests/unit/test_mcp_server.py` — which imports `FastMCP` directly
      and asserts `isinstance(server, FastMCP)`
      (`tests/unit/test_mcp_server.py:12,54-55`), and pokes
      `server._tool_manager._tools` twice more (`:126-127`, `:160`) — is
      updated: `MCPServer` import/isinstance check; the
      `_tool_manager._tools` pokes may need no change if the guard added
      above is transparent to callers that already expect the attribute
      to exist (confirm, don't assume).
- [x] `tests/unit/test_tools_common.py` requires **no code change** and
      **passes unmodified** — this is the existing positive test that
      `@clasi_tool`'s NONE-sentinel stripping still works, exercised
      against synthetic functions with zero FastMCP/MCPServer dependency
      (see its own module docstring). If this file needs a change to
      pass, something in this ticket's implementation broke the
      decoupling sprint 030 built — stop and reconsider the change, don't
      edit the test to match.
- [x] A local smoke test: with the code changes above complete and
      `mcp==2.0.0` installed in a **disposable scratch venv** (not the
      live dev environment), `clasi mcp` starts and reaches "CLASI MCP
      server ready" in its log with no traceback. Do this *before* the
      next step.
- [x] `pyproject.toml`'s `mcp>=1.0,<2.0` cap is removed — **only after**
      the scratch-venv smoke test above passes, as the last step of this
      ticket, per sprint.md Migration Concerns item 1. Do not remove the
      cap earlier "to test against the real thing" — that risks pulling
      `mcp==2.0.0` into the team-lead's own live MCP session mid-ticket.
      Re-check `pip index versions mcp` before this step in case a newer
      2.x release exists; verify against the latest available.
- [x] This ticket's commits are kept small and self-contained (ideally
      one commit, or a small tight range) — see Process Notes: a clean
      `git revert` is the rollback mechanism if the end-of-sprint E2E
      surfaces a problem this ticket's own local verification missed.

## Implementation Plan

**Approach**, in this exact order (see sprint.md Migration Concerns item
1 for why the order matters, not just the content):

1. Set up a disposable scratch venv with `mcp==2.0.0` installed (e.g.
   `python3 -m venv /tmp/mcp2x-check && /tmp/mcp2x-check/bin/pip install
   mcp==2.0.0`) — separate from this project's own `.venv`. Use it to
   confirm import paths as you go, not just at the end.
2. Make the code changes in `mcp_server.py` per the Acceptance Criteria
   above (import rename, `_mcp_server`→`_lowlevel_server`, guard
   `_tool_manager._tools`).
3. Update `tests/unit/test_mcp_server.py` for the rename.
4. Run the scoped test suite (see Testing below) — still against this
   project's normal `.venv` at this point, which still has `mcp` 1.x
   installed via the untouched `pyproject.toml` cap. The code changes
   above should not break anything under 1.x either, since
   `mcp.server.mcpserver` doesn't exist under 1.x — **this step will
   fail until step 5 below is done in the scratch venv, not this
   project's own environment.** Do not "fix" this by pointing the
   project's own venv at `mcp==2.0.0` yet.
5. In the scratch venv from step 1, with this repo's source on
   `PYTHONPATH` (or an editable install into the scratch venv
   specifically — do not touch this project's own `.venv`), run `clasi
   mcp` and confirm "CLASI MCP server ready", then run the scoped test
   suite against that same scratch venv.
6. Only once step 5 is fully green: remove `pyproject.toml`'s cap, run
   `uv sync` (or this project's normal dependency-sync command) to bring
   the project's own `.venv` up to `mcp==2.0.0`, and re-run the scoped
   test suite one final time in the normal dev environment to confirm
   nothing about the sync itself (as opposed to the code) introduced a
   problem.
7. Commit. Keep this ticket's commits small and self-contained (see
   Acceptance Criteria's last item and Process Notes).

**Files to modify:**
- `src/clasi/mcp_server.py`
- `tests/unit/test_mcp_server.py`
- `pyproject.toml` (last step only)

**Files verified but not modified** (state this explicitly in the
commit message or PR description, since "verified unchanged" is itself
a claim someone should be able to check later):
- `src/clasi/tools/_common.py`
- `tests/unit/test_tools_common.py`

**Testing plan:**
- Scoped foreground runs at each stage per the Approach above — never
  run the full suite for this ticket; that happens once at
  `close_sprint`.
- The end-of-sprint E2E run (owned by the team-lead, not this ticket) is
  the final, fresh-dependency-resolve proof — see Process Notes for what
  it needs to check and why this ticket cannot substitute for it.

**Documentation updates:**
- None beyond this ticket and the sprint's `design/` overlay
  (`DESIGN.md`, `tools-DESIGN.md`), already written during planning.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_mcp_server.py tests/unit/test_tools_common.py -v`
  (run once against the scratch venv per Implementation Plan step 5,
  once against the project's own venv per step 6 — not the same run).
- **New tests to write**: none required — `test_tools_common.py` already
  covers the NONE-sentinel positive-test requirement; extend
  `test_mcp_server.py` only as needed for the `MCPServer` rename, not
  with new test cases.
- **Verification command**: `uv run pytest tests/unit/test_mcp_server.py tests/unit/test_tools_common.py -v`

## Process Notes

- Guards fail closed in this project — if a role-guard or mcp-guard
  blocks a write you believe is in scope, **STOP and report it** rather
  than routing around it (no `sed -i`, no shell redirection, no `git
  apply` as a workaround). Reporting a block is a successful outcome of
  this ticket, not a failure.
- Tier-2 (a ticket in `in-progress` status under a locked sprint) may
  edit files under this sprint's own `tickets/` tree directly. Edit this
  ticket's frontmatter/checkboxes as you work; leave the `status: done`
  transition and the `tickets/done/` move to the team-lead's
  `update_ticket_status(path, "done")` call — that call now performs
  both in one step (sprint 030), so do not call `move_ticket_to_done`
  separately and do not move the file yourself.
- **Rollback, if `clasi mcp` will not start after this ticket's changes
  land** (discovered by this ticket's own smoke test, or later by the
  end-of-sprint E2E): revert this ticket's commit(s) as a unit (`git
  revert`, never `git reset --hard` on shared history — this repo's own
  git safety protocol). This must restore **both** the `pyproject.toml`
  cap **and** the `mcp_server.py` code change together — restoring the
  cap alone, without reverting the `MCPServer`/`mcp.server.mcpserver`
  import, leaves `mcp_server.py` importing a module that does not exist
  under `mcp` 1.x, which is an unconditional `ImportError` with no
  fallback, strictly worse than the pre-migration state. After
  reverting: reinstall the editable dev install (this project's `.venv`
  editable convention, not `pipx` — see project memory note "clasi
  install & MCP runtime"), then **restart the Claude Code session** so a
  fresh MCP server subprocess picks up the reverted code. Verify with a
  manual `clasi mcp` shell invocation *before* trusting a new session to
  reconnect — a session that starts against a still-broken server has no
  tools left to report the problem with.
- **What the end-of-sprint E2E run needs to check for this ticket**
  (do not treat "the E2E passed" as automatic proof of this — read its
  report specifically for these): (1) the E2E's container build performs
  a genuinely fresh dependency resolve (no lockfile) and picks up
  `mcp==2.0.0` or later, not a cached 1.x wheel; (2) `clasi mcp` starts
  inside the container with no traceback, reaching "CLASI MCP server
  ready"; (3) at least one real tool call succeeds end-to-end through the
  subject session; (4) — the check nothing else in this ticket can
  substitute for — a tool call made with an omitted optional argument
  (the `"NONE"`-sentinel path, per
  `.claude/rules/tool-call-empty-args.md`) is confirmed via the E2E's
  captured `mcp-calls.jsonl` trace or subject transcript to have reached
  the tool function as Python `None`, not the literal string `"NONE"`.
  Check (4) is fail-open-specific: a broken migration can pass (1)-(3)
  and still silently reintroduce the exact regression this issue exists
  to prevent, because a crash is loud and a leaked `"NONE"` string is
  not.
- Sequencing note: this ticket is intentionally ordered *after* ticket
  001 (uninstall correctness) in this sprint, for risk isolation, not a
  code dependency — see ticket 001's own Process Notes.
