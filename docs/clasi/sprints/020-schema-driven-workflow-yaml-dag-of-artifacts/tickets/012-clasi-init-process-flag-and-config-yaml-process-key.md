---
id: "012"
title: "clasi init --process flag and config.yaml process key"
status: todo
use-cases: [SUC-006]
depends-on: ["010", "011"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# clasi init --process flag and config.yaml process key

## Description

Add a `--process` option to `clasi init` that accepts `se` (default) or
`solo`. When specified, `init_command.py` writes a `process: <value>` key
to `.clasi/config.yaml` in the target directory. Server startup reads this
key to select the schema path.

This ticket enables `clasi init --process solo` as described in SUC-006. The
server-startup wiring that reads `.clasi/config.yaml` to select the active
schema is also part of this ticket.

## Acceptance Criteria

- [ ] `clasi init` gains a `--process [se|solo]` option, default `se`.
- [ ] `clasi init --process solo .` writes `process: solo` to `.clasi/config.yaml` (creating the file and directory if absent).
- [ ] `clasi init` with no `--process` flag writes `process: se` to `.clasi/config.yaml`.
- [ ] Server startup reads `.clasi/config.yaml` `process:` key to determine the active schema path; falls back to `se` if the key is absent.
- [ ] An unknown `--process` value (e.g., `--process foo`) fails with a clear error message before touching any files.
- [ ] `clasi init --process solo` followed by server startup selects `solo-process/schema.yaml`.
- [ ] Existing `clasi init` behavior (platform selection, plugin mode, etc.) is unchanged.
- [ ] Tests: `clasi init --process solo` writes correct config; `clasi init` with no flag writes `se`; unknown value rejects.
- [ ] `uv run pytest` passes.

## Implementation Plan

**Approach**: In `cli.py`, add `@click.option("--process", type=click.Choice(["se", "solo"]), default="se", show_default=True)` to the `init` command. Pass `process` to `run_init()`. In `init_command.py`, after creating `.clasi/`, write `process: <value>` to `.clasi/config.yaml` using PyYAML `safe_dump`.

For server startup, add a helper `get_active_schema_path(project_root: Path) -> Path` in `clasi/schemas/__init__.py` that reads `.clasi/config.yaml` and returns the path to the selected schema. The MCP server startup calls this helper.

**Files to modify**:
- `clasi/cli.py` — add `--process` option
- `clasi/init_command.py` — write `process:` to config.yaml
- `clasi/schemas/__init__.py` — add `get_active_schema_path()` helper
- `clasi/mcp_server.py` — call `get_active_schema_path()` at startup (or wherever server init happens)

**Testing plan**: Use `CliRunner` for the CLI tests. For server startup, mock
`.clasi/config.yaml` in a tempdir and verify `get_active_schema_path()` returns
the correct path.

**Documentation updates**: None in this ticket.
