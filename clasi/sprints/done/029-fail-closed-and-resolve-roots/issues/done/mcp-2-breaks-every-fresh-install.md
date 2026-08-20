---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- dependencies
- p0
sprint: 029
tickets:
- 029-001
---

# P0: mcp 2.0 breaks every fresh install (unbounded `mcp>=1.0`)

## Description

**Discovered by the sprint-028 baseline E2E run on 2026-08-20 — the first
run of the newly instrumented harness, on its first attempt.**

`pyproject.toml:24` declares `mcp>=1.0` with no upper bound. This repo's
`uv.lock` pins `mcp 1.26.0`, so the dogfooded checkout works. Any
environment that resolves dependencies fresh — the E2E container, CI, or
any consumer running `pip install clasi` — now gets **mcp 2.0.0**, which
**removed `mcp.server.fastmcp` entirely**. Verified in the container:

```
mcp version: 2.0.0
mcp.server submodules: __main__, _otel, _streamable_http_modern, apps, auth,
  caching, connection, context, elicitation, extension, lowlevel, mcpserver,
  models, request_state, runner, session, sse, stdio, streamable_http,
  streamable_http_manager, subscriptions, transport_security, validation
fastmcp FAIL: No module named 'mcp.server.fastmcp'
```

`src/clasi/mcp_server.py:16` does `from mcp.server.fastmcp import FastMCP`,
so the import fails hard. The observed crash was **not** in the MCP server
itself but in `clasi init`:

```
clasi/cli.py:85 init
  → clasi/init_command.py:187 run_init
  → clasi/platforms/claude.py:451 install
  → clasi/platforms/claude.py:253 _install_plugin_content
  → from clasi.tools.process_tools import resolve_skill_body
  → clasi/tools/process_tools.py:28 from clasi.mcp_server import ...
  → clasi/mcp_server.py:16 from mcp.server.fastmcp import FastMCP
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

**Impact: CLASI is currently uninstallable-and-unusable for every new
user.** `clasi init` — the very first command anyone runs — crashes.

## Two defects, not one

1. **Unbounded dependency.** `mcp>=1.0` admits a major version that
   deleted the API CLASI is built on. The lockfile masked this from
   everyone working in this repo.
2. **`clasi init` should never need FastMCP.** It pulls the entire MCP
   server import chain in order to call one pure helper
   (`resolve_skill_body`). This is the same anti-pattern the reliability
   review flagged for `dispatch_log` (03-hooks-guards.md F11) and the
   same import-cost trap sprint 027 fixed for the hook path. A CLI
   install path must not depend on the server module.

## Related exposure (do not fix here, but record)

The reliability review's 02-mcp-tools.md F5 warns that the `"NONE"`
sentinel stripping and call logging are installed by monkey-patching MCP
library internals (`_tool_manager.call_tool`, `_mcp_server.instructions`,
`JSONRPCMessage.model_validate_json`). Under mcp 2.x those attributes do
not exist, so even after the import is fixed, the sentinel stripping
would silently stop working — a fail-open, not a crash. Any future
migration to mcp 2.x must land the owned `@clasi_tool` decorator
(`uniform-mcp-tool-envelope.md`, sprint 030) FIRST.

## Acceptance criteria

- [ ] `pyproject.toml` caps the dependency at `mcp>=1.0,<2.0` (or pins a
      known-good range), so a fresh resolve cannot pick up the
      incompatible major.
- [ ] `clasi init` no longer imports `clasi.mcp_server`: move
      `resolve_skill_body` (and any other pure helper the installers
      need) out of `process_tools` into a module that does not import
      FastMCP, or import it lazily inside the function that uses it.
- [ ] A test asserts `clasi init`'s import chain is free of
      `clasi.mcp_server` / `mcp.server.fastmcp` — e.g. import the install
      path in a subprocess with `mcp` shadowed by a stub that raises on
      `mcp.server.fastmcp`, and assert init still works.
- [ ] The E2E container reaches a running Claude Code session (the
      failure that surfaced this).
- [ ] A follow-up issue is filed for the actual mcp 2.x migration; it is
      explicitly NOT in scope here.
