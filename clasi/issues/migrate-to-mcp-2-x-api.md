---
status: pending
type: task
tags:
- reliability-campaign
- dependencies
- mcp
- mcp-2x-migration
blocked-by: uniform-mcp-tool-envelope.md
---

# Migrate CLASI's MCP server to the mcp 2.x API

## Description

Deferred follow-up from sprint 029 ticket 001 ("mcp dependency cap and
install-path decoupling"). That ticket capped the `mcp` dependency at
`mcp>=1.0,<2.0` in `pyproject.toml` (a fresh resolve had been picking
up `mcp==2.0.0`, which deleted `mcp.server.fastmcp` entirely and broke
`clasi init` for every new install — see
`clasi/issues/mcp-2-breaks-every-fresh-install.md`) and decoupled
`clasi init`'s install path so it no longer imports `clasi.mcp_server`
at all. It deliberately did **not** migrate CLASI's own MCP server
implementation to the mcp 2.x API — that is this issue.

**Do not attempt this migration as a quick follow-on.** It is
substantially harder than the import-chain decoupling ticket 001 did.

## Why it's hard

Per `docs/reviews/2026-08-reliability/02-mcp-tools.md` finding F5,
CLASI's `"NONE"`-sentinel argument stripping and call-trace logging
(`src/clasi/mcp_server.py`: `_strip_none_sentinel` and the code that
installs it) are implemented by monkey-patching **private FastMCP
internals** — `_tool_manager.call_tool`, `_mcp_server.instructions`,
`JSONRPCMessage.model_validate_json`. mcp 2.x removed
`mcp.server.fastmcp` entirely and does not expose these same
internals. A naive migration would make the NONE-sentinel stripping
**silently stop working** (fail-open: tool calls would receive the
literal string `"NONE"` instead of `None`) rather than crash loudly —
a dangerous, hard-to-notice regression class, not a build break.

## Required precondition

Per the same review finding, this migration must wait until the owned
`@clasi_tool` decorator lands (`clasi/issues/uniform-mcp-tool-envelope.md`,
tracked for sprint 030). That decorator is meant to replace the
monkey-patched internals with an owned envelope that does not depend
on FastMCP's private implementation details — NONE-sentinel stripping
becomes owned code instead of a patch onto library internals, so it
survives the mcp 2.x API surface change instead of silently
disappearing with it. Do not attempt the mcp 2.x migration before that
decorator exists.

## Scope for the eventual migration

- Update `src/clasi/mcp_server.py`'s `from mcp.server.fastmcp import
  FastMCP` and all FastMCP-specific usage to the mcp 2.x API surface
  (`mcp.server.mcpserver`, or whatever the 2.x equivalent is by the
  time this is picked up).
- Re-implement NONE-sentinel stripping and call-trace logging against
  the new API's public extension points (via the `@clasi_tool`
  decorator from `uniform-mcp-tool-envelope.md`), not monkey-patched
  internals.
- Remove the `mcp>=1.0,<2.0` cap in `pyproject.toml` once the server
  is verified working against 2.x.
- Re-verify under a fresh dependency resolve exactly as ticket 001
  did: `uv build --wheel`, fresh `pip install` of the wheel in a
  throwaway container (no lockfile involved), confirming both `clasi
  init` and `clasi mcp` work end-to-end.

## Acceptance criteria

- [ ] `@clasi_tool` decorator (`uniform-mcp-tool-envelope.md`) has
      landed first.
- [ ] `mcp_server.py` runs against mcp 2.x with no import of
      `mcp.server.fastmcp`.
- [ ] NONE-sentinel stripping and call-trace logging work under mcp
      2.x, exercised by unit tests (not only reachable through the
      live server path).
- [ ] `mcp>=1.0,<2.0` cap removed from `pyproject.toml`.
- [ ] Fresh-resolve container verification (wheel build + throwaway
      `pip install`, no lockfile) confirms `clasi init` and `clasi mcp`
      both work.

## Priority

Not urgent — explicitly deferred until its precondition
(`uniform-mcp-tool-envelope.md`) lands. The `mcp>=1.0,<2.0` cap in
`pyproject.toml` fully neutralizes the immediate breakage in the
meantime.
