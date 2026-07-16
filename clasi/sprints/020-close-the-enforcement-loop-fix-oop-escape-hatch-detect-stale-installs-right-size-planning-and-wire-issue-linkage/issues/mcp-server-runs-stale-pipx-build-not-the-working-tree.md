---
status: in-progress
type: bug
tags:
- install
- mcp
- tooling
- correctness
sprint: '020'
tickets:
- 020-002
---

# The MCP server runs a stale pipx build, not the working tree

## Description

`.mcp.json` starts the CLASI MCP server with the bare command `clasi`, which
resolves through `$PATH` to whatever build happens to be installed globally —
not to the code in the working tree. There is nothing tying the two together,
so they drift silently and without limit.

**This is not a theoretical risk. It produced a wrong artifact on 2026-07-15.**

When sprint 019 closed, `close_sprint` archived it with `status: done` — the
exact defect ticket `019-007` had just fixed and merged. Measured at the time:

| | version | `Sprint.archive()` writes |
|---|---|---|
| working tree | `0.20260715.2` | `closed` ✓ |
| pipx build (what `clasi` resolves to) | `0.20260627.12` | `done` ✗ |

Eighteen days of drift. The fix was correct, merged, and covered by three
regression tests that were verified to fail against the old writer — and none
of that mattered, because the tool doing the closing was running code from
before the sprint began.

The failure is silent. Nothing warned that the server was stale; the close
reported `"status": "success"`. The only reason it was caught is that the
end-state was checked by hand against what the ticket promised.

## Blast radius

Every MCP tool call in a session goes through this server, so the whole of
sprint 019's work was inert wherever it was reached via MCP or hooks:

- **Enforcement guards (tickets 001-004)**: the payload-parsing fix, the OOP
  helper, caller-keyed tier resolution, and the ticket-state gate were all
  live in the tree but absent from the running hooks. Verification with
  `uv run clasi hook role-guard` passed while the actual hook — invoked as
  bare `clasi hook role-guard` from `.claude/settings.json` — ran the stale
  build. **The verification and the production path were different code.**
- **Status block (ticket 006)**: the tree emits 2,113 bytes; the hooks kept
  emitting the 37KB version.
- **Archive writer (ticket 007)**: demonstrated above.

Note the hooks in `.claude/settings.json` and `plugin/hooks/hooks.json` invoke
bare `clasi hook ...` for the same reason and have the same exposure.

## Cause

`.mcp.json`:

```json
{"mcpServers": {"clasi": {"command": "clasi", "args": ["mcp"]}}}
```

`init_command._detect_mcp_command()` (`src/clasi/init_command.py:38-52`) hard-codes
this and documents the reasoning: an earlier `uv run clasi mcp` form was
dropped because it "was only useful when CLASI was being developed locally and
broke for any project that didn't have uv or didn't have a `[project]` table in
pyproject.toml."

That reasoning is sound *for consumer projects* and wrong *for this repo*, which
develops the very tool it runs. The docstring even anticipates it: "Projects
that actually want `uv run` can edit their MCP config by hand." Nobody did, and
nothing detects that nobody did.

So the defect is not the bare `clasi` default — it is that there is no
staleness detection anywhere, in either mode.

## Proposed fix

Layered; (1) is the floor and is cheap.

1. **Detect and report staleness.** The server already has everything needed:
   `get_version()` returns `version`, `metadata_version`, and `source_path`
   specifically "so staleness is detectable" (its own docstring). Nothing acts
   on it. Compare the running server's `source_path` against the project's own
   tree at startup and warn loudly — into the status block, the MCP
   `instructions` field, or a startup log line — when the server is running
   from outside the project it is managing. This catches the failure in every
   mode without changing anyone's install.
2. **Fail closed on a dangerous mismatch.** A stale *guard* is worse than no
   guard: it reports success while enforcing nothing. Consider refusing to
   serve, or degrading loudly, when the version gap is large.
3. **Make this repo's own `.mcp.json` point at the editable install.** A
   dogfooding checkout should run the code under development. Either commit a
   `uv run`-form config for this repo specifically, or document the manual edit
   the docstring already suggests — but pair it with (1), because
   documentation is what failed here.

Do NOT simply re-run `pipx install --force` and call it fixed. That resolves
today's drift and leaves the detection gap that allowed it.

## Verification

- With a deliberately stale install (e.g. pin pipx to an older version) and a
  newer working tree, starting the MCP server produces a visible staleness
  warning naming both versions.
- A fresh `clasi init` in a consumer project (no uv, no `[project]` table) still
  works — the fix must not reintroduce the breakage that motivated the bare
  `clasi` default in the first place.
- `close_sprint` on a repo whose tree contains the 019-007 writer fix produces
  `status: closed`, not `done`.

## Related

- Directly caused sprint 019 to archive as `status: done`. That artifact is
  **left as-is deliberately** — it is an accurate record of what happened, and
  rewriting it is the same move rejected in `019-007`'s Part B. See
  `clasi/issues/detect-inconsistencies-drift-checks-terminal-archived-sprints.md`.
- `src/clasi/init_command.py:38-52` documents why bare `clasi` was chosen; that
  rationale is not wrong, it is just silent about staleness.
- Relevant to the installation-footprint discussion: any design that serves
  process content from the installed package (see
  `clasi/issues/issue-re-enable-the-mcp-process-content-tools.md`) inherits this
  problem and makes it worse — skills would come from the stale build too.
