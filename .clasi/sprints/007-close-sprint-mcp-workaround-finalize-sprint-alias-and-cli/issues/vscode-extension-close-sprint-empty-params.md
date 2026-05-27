---
status: in-progress
sprint: '007'
tickets:
- 007-001
---

# `close_sprint` arrives with empty params from Claude Code VS Code extension

## Status update — 2026-05-26: alias result is in

Sprint 007 shipped both workarounds. The affected user reinstalled
clasi and reran the diagnostic. **Result: `finalize_sprint` fails
identically to `close_sprint` — both arrive with `input_value={}`.**

**The tool name is NOT the trigger.** Two tools with different names
and identical Python signatures fail in exactly the same way. The
cause is structural — something in the schema fingerprint.

Remaining candidates, in order of distinctiveness vs. working tools
(per the upstream agent's analysis in the updated bug report):

1. **Boolean optionals with `default: true`** (`push_tags`,
   `delete_branch`). Unique to the failing schema — no working tool
   has any boolean params.
2. **String optionals with a non-null default** (`main_branch="master"`).
   Also unique to the failing schema. Working tools' string optionals
   are all `anyOf [string, null]` with `default: null`.
3. **Total optional-param count** — 5 optionals here vs ≤2 on working
   tools.
4. **Mixed `anyOf [string, null]` defaults and plain-type defaults**
   coexisting in the same schema.

### Next experiment (proposed)

A single cleanly-shaped alias that matches `get_status`'s shape would
test the schema-fingerprint hypothesis from the other direction:

```python
@server.tool()
def finalize_sprint_min(
    sprint_id: str,
    branch_name: Optional[str] = None,
    test_command: Optional[str] = None,
) -> str:
    """Minimal-schema alias for close_sprint."""
    return close_sprint(sprint_id, branch_name=branch_name,
                        test_command=test_command)
```

- **If this succeeds** → the cause is "one or more of booleans /
  non-null string default / count". Bisect with two more aliases (one
  re-adding the booleans, one re-adding `main_branch`) to localize.
- **If this fails too** → the trigger is something even more basic
  than expected. Fall back to the wire-trace ask in the bug report.

The CLI subcommand (`clasi sprint close`) remains the unconditional
unblock path regardless of how this resolves.

The CLI subcommand (`clasi sprint close`) remains the unconditional
unblock path regardless of how the structural diagnostic resolves.

---

Downstream CLASI user (inventory project) reports that
`mcp__clasi__close_sprint` calls from the Claude Code VS Code extension
arrive at the MCP server with `input_value={}`, producing a Pydantic
`Field required` error for `sprint_id`. Affects clasi `0.20260516.1`,
Opus 4.7, VS Code Claude Code extension. The Python `mcp` SDK over the
same `clasi mcp` stdio transport works correctly.

**Full bug report (updated 2026-05-25 with diagnostic results):**
`/Volumes/Proj/proj/league-projects/infrastructure/inventory/docs/bug-reports/2026-05-25-claude-code-close-sprint-empty-params.md`

## What the diagnostic localized

A targeted test was run in the affected session. Results (full table in
the bug report):

- `close_sprint(sprint_id="002")` — **FAIL**, `input_value={}`. Even
  the minimal call with only the required field is stripped.
- `get_status(sprint_id, ticket_id)` — **SUCCESS**. This tool has the
  same `anyOf [string, null]` default-null pattern as close_sprint's
  optional params.
- `close_sprint(sprint_id, <one_optional>)` for each of the four
  optionals — all **FAIL** identically with `input_value={}`.

Conclusions:

- **Not the `anyOf [string, null]` shape on optional params.**
  `get_status` succeeds with the same shape.
- **Not the optional-param surface.** Step 1 reproduces with zero
  optionals.
- **Not any one optional field in isolation.** Each isolated optional
  fails the same way.
- The dict is dropped wholesale, for `close_sprint` specifically,
  before reaching the MCP server.

We do **not** know which property of `close_sprint` is the trigger.
Compared to the working tools in the report, close_sprint is distinct
along multiple axes — any of these could be the cause:

- **Boolean optionals with `True` defaults** (`push_tags=True`,
  `delete_branch=True`). No working tool in the comparison has any
  boolean params.
- **Total param count** — 6 params (1 required + 5 optional). The
  working tools cap at ~2 params.
- **Mixed default types in one signature** — string default
  (`"master"`), boolean defaults, and `None` defaults coexist.
- **The tool name itself.**
- **Docstring shape** (long, multi-paragraph, with structured "Args:"
  block). Less likely but not ruled out.

Logging is already adequate to support diagnosis: the MCP server wraps
`_tool_manager.call_tool` at `mcp_server.py:154-169` and logs every
incoming call's args dict — which is exactly what produced the
`input_value={}` evidence. Adding logging inside close_sprint itself
wouldn't help; Pydantic rejects the call before the function body
runs.

## Workarounds that don't work

- **Legacy `close_sprint(sprint_id)` only.** Confirmed broken — even
  the bare call arrives as `{}`, so the legacy fallback path inside
  the tool is unreachable.
- **`clasi close-sprint` CLI.** Confirmed not viable — the clasi CLI
  has no close-sprint subcommand (top-level commands: hook, init,
  install, mcp, migrate, schema, status, tool, uninstall).
- **Manually closing via MCP primitives.** Possible but tedious and
  error-prone (must hand-roll archive + state DB update + git merge +
  tag + branch delete).

## Workaround that does work

- **Python `mcp` SDK over stdio** (script in the bug report). The
  affected user has saved this to project memory.

## Recommended clasi-side actions

Given the diagnostic, the two highest-leverage moves on our side are
both small and independent of each other. Either alone unblocks the
user. Doing both gives us a cheap diagnostic confirmation *and* a
durable CLI escape hatch.

### Action 1 (high value, ~30 min): Add a `clasi sprint close` CLI subcommand

Wire the existing `close_sprint` function into the click CLI in
`clasi/cli.py`. The function already exists in
`clasi/tools/artifact_tools.py:973` — just needs a thin click wrapper:

```python
@cli.group()
def sprint() -> None:
    """Sprint lifecycle commands."""

@sprint.command("close")
@click.argument("sprint_id")
@click.option("--branch", "branch_name", default=None)
@click.option("--main-branch", default="master")
@click.option("--push-tags/--no-push-tags", default=True)
@click.option("--delete-branch/--no-delete-branch", default=True)
@click.option("--test-command", default=None)
def sprint_close(sprint_id, branch_name, main_branch, push_tags,
                 delete_branch, test_command):
    from clasi.tools.artifact_tools import close_sprint
    click.echo(close_sprint(sprint_id, branch_name, main_branch,
                            push_tags, delete_branch, test_command))
```

This gives any affected user (now and in the future, for any similar
MCP-layer bug) a clean Bash-shellable escape hatch:

```bash
clasi sprint close 002 --branch sprint/002-foo
```

Generalizes well — we should probably expose the other lifecycle
operations (`advance-phase`, `acquire-lock`, etc.) the same way over
time, but `close` is the one with an active bug forcing the issue.

### Action 2 (cheap, ~10 min): Register a tool-name alias

Add a second `@server.tool()` registration that wraps `close_sprint`
under a different name — e.g. `finalize_sprint`:

```python
@server.tool()
def finalize_sprint(
    sprint_id: str,
    branch_name: Optional[str] = None,
    main_branch: str = "master",
    push_tags: bool = True,
    delete_branch: bool = True,
    test_command: Optional[str] = None,
) -> str:
    """Alias for close_sprint. See close_sprint docs."""
    return close_sprint(sprint_id, branch_name, main_branch,
                        push_tags, delete_branch, test_command)
```

This isolates **name** as the only variable: every other property
(boolean defaults, param count, mixed types, docstring) stays
identical. So the test cleanly disambiguates two cases:

- If `finalize_sprint` works for the affected user → the name was
  the trigger. The alias becomes the permanent workaround.
- If `finalize_sprint` also fails → the name is not the trigger;
  the cause is in the param shape. Most likely candidate next would
  be the boolean-with-True-default pattern, since that's the most
  distinctive structural difference vs. working tools. A follow-up
  alias removing the booleans would narrow further.

Either outcome tells us what to fix next. Unblock comes from
Action 1 (CLI) regardless of how the alias test resolves.

### Action 3 (after Action 1+2): File upstream bug

Once we have a concrete repro and the alias result, file against the
Claude Code VS Code extension repo with:

- Bug report doc
- The alias result (name-vs-schema disambiguation)
- A pointer to clasi 0.20260516.1 as a minimal reproducer

## Recommendation

Do Action 1 and Action 2 in a single small sprint. Ship as a patch
release. Then run the alias test against the affected user's session
to lock down the cause before filing upstream.
