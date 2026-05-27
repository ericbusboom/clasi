---
id: '007'
title: "close_sprint MCP Workaround \u2014 finalize_sprint Alias and CLI"
status: done
branch: sprint/007-close-sprint-mcp-workaround-finalize-sprint-alias-and-cli
use-cases:
- SUC-001
- SUC-002
issues: []
todos:
- /Volumes/Proj/proj/code-projects/dotconfig/docs/clasi/todo/vscode-extension-close-sprint-empty-params.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 007: close_sprint MCP Workaround — finalize_sprint Alias and CLI

## Goals

Provide two workarounds for a confirmed VS Code extension bug where
`mcp__clasi__close_sprint` calls arrive at the MCP server with an empty params
dict (`input_value={}`), causing a Pydantic `Field required` error for
`sprint_id`. The bug blocks affected users from closing sprints via the
extension.

## Problem

The Claude Code VS Code extension drops the params dict for `close_sprint` MCP
calls before they reach the server. Diagnostic testing confirmed the failure is
total (even the minimal bare call with only `sprint_id` arrives as `{}`), and
is specific to this tool — other tools with similar parameter shapes succeed.
The root cause is not yet isolated; candidates include the tool name, boolean
parameters with `True` defaults, total param count, or docstring shape.

No CLI escape hatch exists today: `clasi` has no `sprint close` subcommand.
The only working workaround requires the user to invoke the Python MCP SDK
directly over stdio.

## Solution

Two independent changes, each addressing a different angle:

**Action 1 — `clasi sprint close` CLI subcommand**: Wire the existing
`close_sprint` function into the click CLI as a `clasi sprint` group with a
`close` subcommand. This gives any affected user (now and in the future) a
shell-invokable escape hatch independent of the MCP layer.

**Action 2 — `finalize_sprint` MCP tool alias**: Register a second
`@server.tool()` with the name `finalize_sprint` that delegates to
`close_sprint` with an identical Python signature. The name is the only
changed variable, making this a clean diagnostic: if the alias works, the
tool name was the trigger; if it also fails, the cause is structural.

## Success Criteria

- `clasi sprint close <sprint_id>` executes a full sprint close from the
  shell without going through the MCP layer.
- `mcp__clasi__finalize_sprint` is registered and callable with the same
  parameters as `close_sprint`.
- The `finalize_sprint` alias has an identical Python signature to
  `close_sprint` — same param names, defaults, types, and order. This is
  non-negotiable; any deviation invalidates the diagnostic value.
- Existing `close_sprint` behavior is unchanged.
- Tests pass.

## Scope

### In Scope

- Add `clasi sprint` click group with `close` subcommand (`clasi/cli.py`)
- Add `finalize_sprint` MCP tool alias (`clasi/tools/artifact_tools.py`)
- Unit tests for the new CLI command
- Unit test confirming `finalize_sprint` signature matches `close_sprint`

### Out of Scope

- Filing the upstream VS Code extension bug (Action 3 in the TODO) — deferred
  until after the alias diagnostic result is observed
- Any changes to `close_sprint` internals or behavior
- Any logging changes (existing MCP wrapper already logs args dicts)
- Other lifecycle CLI subcommands (`advance-phase`, `acquire-lock`, etc.) —
  noted as future work but not part of this sprint

## Test Strategy

- CLI test: invoke `clasi sprint close --help` and verify it appears in the
  CLI command listing. A minimal integration test (mocked `close_sprint`) can
  verify the click wiring and option plumbing.
- Alias test: use `inspect.signature` to assert that `finalize_sprint` and
  `close_sprint` have identical parameter names, annotations, and defaults.
- Run the full `uv run pytest` suite to confirm no regressions.

## Architecture Notes

The `clasi sprint` group pattern is chosen over a flat `clasi close-sprint`
command because `cli.py` already has precedent for sub-groups (`tool`,
`schema`). Lifecycle operations (`close` today, potential `advance-phase`,
`acquire-lock`, etc. in the future) are cohesively grouped under `sprint`.
The additional indirection cost is a single `cli.group()` decorator — minimal.

The `finalize_sprint` alias is placed in `artifact_tools.py` immediately after
`close_sprint`, as a one-function wrapper with a minimal docstring. It must not
reimplement any logic — it calls `close_sprint` directly.

## GitHub Issues

(None linked yet.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 007-001 | Add `clasi sprint close` CLI subcommand | — |
| 007-002 | Add `finalize_sprint` MCP tool alias | — |

Tickets execute serially in the order listed.
