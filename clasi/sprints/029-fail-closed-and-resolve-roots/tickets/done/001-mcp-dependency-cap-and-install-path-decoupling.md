---
id: '001'
title: mcp dependency cap and install-path decoupling
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: mcp-2-breaks-every-fresh-install.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# mcp dependency cap and install-path decoupling

## Description

**This ticket is the reliability campaign's current hard blocker.**
Nothing in this sprint — or the two sprints after it — can be
validated against the instrumented E2E until `clasi init` stops
crashing on a fresh dependency resolve. Discovered by the sprint-028
baseline E2E run's very first attempt, immediately after the container
build.

Two independent defects, both fixed here: (1) `pyproject.toml:24`'s
unbounded `mcp>=1.0` dependency resolves to `mcp==2.0.0` on any fresh
install, which deleted `mcp.server.fastmcp` entirely; (2) `clasi init`
pulls in that whole import chain merely to call one pure helper
function (`resolve_skill_body`) that has zero actual dependency on the
MCP server. See `clasi/issues/mcp-2-breaks-every-fresh-install.md` for
the full captured traceback.

This ticket touches no enforcement code (`hook_handlers.py` is
untouched) — it carries none of the dogfooding lockout risk later
tickets in this sprint do.

**Scope**: `pyproject.toml`, new `src/clasi/skill_resolve.py`,
`src/clasi/tools/process_tools.py`, `src/clasi/platforms/claude.py`.

**Files to touch (verified during planning):**

- `pyproject.toml:24` — `"mcp>=1.0"` → `"mcp>=1.0,<2.0"`.
- New `src/clasi/skill_resolve.py` — move `resolve_skill_body` verbatim
  from `src/clasi/tools/process_tools.py` (currently lines 262-311),
  plus its `_LOAD_FROM_RE` regex constant and `_PACKAGE_ROOT` constant
  defined just above it. **Trap verified during planning**:
  `_PACKAGE_ROOT` must become `Path(__file__).parent.parent` in the new
  location — `src/clasi/skill_resolve.py` sits one directory level
  shallower than `src/clasi/tools/process_tools.py`, whose own
  `_PACKAGE_ROOT = Path(__file__).parent.parent.parent`. Both must
  resolve to the same `src/` directory (the parent of the `clasi`
  package, used to resolve `clasi/schemas/...`-style `Load from:`
  paths). Get this wrong and every `Load from:` directive in every
  skill silently breaks.
- `src/clasi/tools/process_tools.py` — delete the moved
  function/constants; `get_skill_definition`'s three call sites
  (currently lines 332, 335, 341) import `resolve_skill_body` from
  `clasi.skill_resolve` instead. Nothing else in this module changes —
  it keeps `from clasi.mcp_server import server, content_path,
  get_project` for its other 15+ `@server.tool()` functions.
- `src/clasi/platforms/claude.py` — both call sites (currently lines
  157 and 253) change `from clasi.tools.process_tools import
  resolve_skill_body` to `from clasi.skill_resolve import
  resolve_skill_body`.

## Acceptance Criteria

- [x] `pyproject.toml` caps `mcp` at `>=1.0,<2.0`
- [x] `resolve_skill_body` lives in new `src/clasi/skill_resolve.py`,
      importing nothing from `clasi.mcp_server` (verify with a static
      import check, not just "it works")
- [x] `_PACKAGE_ROOT` in the new module resolves to the same `src/`
      directory the old `tools/process_tools.py` location did — add a
      test that round-trips a real skill using a `Load from:` directive
      and asserts the resolved content is correct
- [x] `process_tools.py`'s `get_skill_definition` still works, now
      importing `resolve_skill_body` from `clasi.skill_resolve`; its
      own `clasi.mcp_server` import for `server`/`content_path`/
      `get_project` is unchanged
- [x] `platforms/claude.py`'s two call sites import from
      `clasi.skill_resolve`
- [x] A test asserts `clasi init`'s import chain is free of
      `clasi.mcp_server` / `mcp.server.fastmcp` — run the install path
      in a subprocess with `mcp.server.fastmcp` shadowed/blocked (e.g. a
      `sys.modules` stub that raises `ImportError` on that submodule)
      and assert `clasi init` still completes successfully
- [x] File (during this ticket, not before) a follow-up issue for the
      actual mcp 2.x migration — it is explicitly NOT implemented here,
      and per `docs/reviews/2026-08-reliability/02-mcp-tools.md` F5 it
      must wait for Phase 3/4's `@clasi_tool` decorator (mcp 2.x removes
      the private FastMCP internals the current NONE-sentinel stripping
      monkey-patches)
- [ ] The E2E container reaches a running Claude Code session (the
      failure that surfaced this) — validated in the sprint's own E2E
      run, not a unit test. **Not run by this ticket's programmer**: a
      full `tests/e2e/start.sh` run needs real subscription credentials
      and spends real model-call budget, which is the stakeholder's
      call to spend, not a subagent's (see "Human-in-the-loop control"
      guidance). Proxy verification done instead, without live
      credentials: `uv build --wheel` + a fresh, throwaway
      `python:3.14-slim` container running a clean `pip install` of the
      wheel (no `uv.lock` involved) confirms (a) the resolve now picks
      `mcp==1.29.0`, not `2.0.0`, and (b) `clasi init .` completes
      end-to-end and writes the full skill/agent/hook/CLAUDE.md
      scaffold. This is the same "fresh resolve" proof `start.sh`
      itself performs before launching Claude Code — it isolates and
      proves the exact reported crash is gone. Recommend the
      team-lead run `tests/e2e/start.sh` for the final live-session
      confirmation and check this box once it passes.

## Testing

- **Existing tests to run**: `uv run pytest tests/system/test_process_tools.py tests/unit/test_platform_claude.py tests/unit/test_init_command.py` (scoped, foreground)
- **New tests to write**: a new `tests/unit/test_skill_resolve.py` (or
  fold into `test_process_tools.py`) covering `resolve_skill_body`'s
  `Load from:` resolution at its new location; the
  import-chain-free-of-`mcp_server` subprocess test described above.
- **Verification command**: `uv run pytest tests/system/test_process_tools.py tests/unit/test_platform_claude.py tests/unit/test_init_command.py -v`
