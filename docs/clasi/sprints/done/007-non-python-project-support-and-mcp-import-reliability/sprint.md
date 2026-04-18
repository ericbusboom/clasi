---
id: '007'
title: Non-Python project support and MCP import reliability
status: done
branch: sprint/007-non-python-project-support-and-mcp-import-reliability
use-cases:
- SUC-001
- SUC-002
- SUC-003
todos:
- hardcoded-pytest-blocks-non-python-projects.md
- fix-mcp-lazy-import-failures.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 007: Non-Python project support and MCP import reliability

## Goals

1. Make CLASI's MCP server fail fast and report clearly when module imports
   are stale, eliminating silent tool failures from `ModuleNotFoundError`.
2. Remove the hardcoded `uv run pytest` assumption from `close_sprint` so
   non-Python projects can close sprints normally.
3. Make rules installed by `clasi init` language-neutral and add
   `.gitignore` to the log directory so it works out-of-the-box for any
   project type.

## Problem

Two related reliability issues make CLASI harder to use in non-Python projects
or after server updates:

- **MCP import failures**: Lazy imports inside `artifact_tools.py` function
  bodies cause `ModuleNotFoundError` for `clasi.sprint`, `clasi.todo`, etc.
  when the server process started from an older source snapshot. Python's
  negative import cache pins the failure for the life of the process, making
  tools like `list_sprints` and `list_tickets` silently fail until the server
  is restarted. `get_version` still works, which misleads operators into
  thinking the server is healthy.

- **Pytest assumption in close_sprint**: `_close_sprint_full` hardcodes
  `uv run pytest` as the test command. Non-Python projects that have `uv`
  installed will get spurious test failures when closing sprints. The
  existing `FileNotFoundError` fallback only handles the case where `uv` is
  missing, not where it exists but pytest is irrelevant.

- **Language-specific rules**: Rules installed by `clasi init` embed
  `uv run pytest` in `source-code.md` and `git-commits.md`, making them
  unsuitable for non-Python projects. The log directory also lacks a
  `.gitignore`, causing log files to surface in `git status` for any project
  type.

## Solution

- Move all lazy imports in `artifact_tools.py` to module level so the server
  fails fast at startup. Add a preflight check in `mcp_server.py` `run()`
  that catches import errors before tools are registered. Enrich `get_version`
  to return the metadata version and source path so staleness is detectable
  from a single call.

- Add `test_command: Optional[str] = None` to `close_sprint` (default
  `None` = `uv run pytest`; empty string `""` = skip tests). Thread the
  parameter through `_close_sprint_full`. Update the close-sprint skill docs.

- Remove `uv run pytest` from the `source-code.md` and `git-commits.md`
  rule templates in `init_command.py`. Add a `docs/clasi/log/.gitignore`
  file during `clasi init` to suppress log files from git.

## Success Criteria

- `list_sprints`, `list_tickets`, and `list_todos` fail at server startup
  (not at first call) when modules are missing.
- `get_version` returns `metadata_version` and `source_path` fields.
- `close_sprint` accepts `test_command=""` to skip tests; `test_command=None`
  still runs `uv run pytest`.
- `clasi init` rules contain no references to `uv run pytest`.
- `clasi init` creates `docs/clasi/log/.gitignore`.

## Scope

### In Scope

- Eager top-level imports in `artifact_tools.py` (all ~15 lazy import sites)
- Preflight import check in `mcp_server.py` `run()`
- `get_version` enrichment (`metadata_version`, `source_path`)
- `test_command` parameter on `close_sprint` / `_close_sprint_full`
- close-sprint skill docs update
- Language-neutral init rule templates (`source-code.md`, `git-commits.md`)
- `docs/clasi/log/.gitignore` created during `clasi init`

### Out of Scope

- Broader multi-language project detection or auto-configuration
- Changes to test runner infrastructure
- Any other MCP tools or process flows

## Test Strategy

Unit tests cover all changed behaviors:

- Import error detection: patch the preflight to raise and verify the
  server aborts with a clear message.
- `get_version` shape: assert `metadata_version` and `source_path` keys.
- `close_sprint` with `test_command=""`: assert subprocess is not called.
- `close_sprint` with `test_command="npm test"`: assert subprocess is called
  with the provided command.
- Init rules: assert neither `source-code.md` nor `git-commits.md` contains
  `uv run pytest` after init.
- Init log gitignore: assert `docs/clasi/log/.gitignore` is created.

## Architecture Notes

All changes are contained within `artifact_tools.py`, `mcp_server.py`,
`process_tools.py`, and `init_command.py`. No new modules are introduced and
no data formats change.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Eager top-level imports in artifact_tools.py and preflight check | — | 1 |
| 002 | Add test_command parameter to close_sprint | — | 1 |
| 003 | Language-neutral init and log .gitignore | — | 1 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
