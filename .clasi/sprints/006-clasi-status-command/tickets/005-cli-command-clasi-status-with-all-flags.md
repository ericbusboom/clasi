---
id: '005'
title: 'CLI command: clasi status with all flags'
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
depends-on:
- '003'
- '004'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# CLI command: clasi status with all flags

## Description

This ticket wires the `clasi/status/` package into the CLI. It adds the
`clasi status` command to `clasi/cli.py` with four flags: `--agent`, `--sprint`,
`--ticket`, and `--format`. The command resolves the agent role, calls
`build_status`, calls `narrow_status`, serializes, and prints.

## Acceptance Criteria

- [x] `clasi status` is a registered command in `clasi/cli.py`.
- [x] Flags: `--agent ROLE` (default: `$CLASI_AGENT_NAME` env var, then `team-lead`), `--sprint ID`, `--ticket ID`, `--format [yaml|json]` (default: `yaml`).
- [x] `clasi status` with no flags prints valid YAML with all required top-level keys.
- [x] `clasi status --format json` prints valid JSON parseable by `json.loads`.
- [x] `clasi status --agent sprint-planner --sprint 006` prints narrowed sprint-planner view.
- [x] `clasi status --agent programmer --ticket 006-003` prints narrowed programmer view.
- [x] If run in a non-CLASI project (no `.clasi/` directory), prints a helpful error message and exits non-zero.
- [x] `clasi status --help` shows flag descriptions.
- [x] CLI tests (integration-style, against this repo's `.clasi/`) in `tests/integration/test_status_cli.py`.
- [x] `uv run pytest tests/integration/test_status_cli.py` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### Approach

Add to `clasi/cli.py`:

```python
@cli.command()
@click.option("--agent", default=None, ...)
@click.option("--sprint", "sprint_id", default=None, ...)
@click.option("--ticket", "ticket_id", default=None, ...)
@click.option("--format", "fmt", type=click.Choice(["yaml", "json"]), default="yaml")
def status(agent, sprint_id, ticket_id, fmt):
    from clasi.status import build_status, narrow_status
    from clasi.status.formatting import to_yaml, to_json
    ...
```

Agent resolution: `agent or os.environ.get("CLASI_AGENT_NAME") or "team-lead"`.

Call `build_status(project, agent=resolved, sprint_id=sprint_id, ticket_id=ticket_id)`.
Call `narrow_status(full, agent=resolved, sprint_id=sprint_id, ticket_id=ticket_id)`.
Serialize with `to_yaml` or `to_json` per `--format`.

### Files to modify

- `clasi/cli.py` — add `status` command

### Files to create

- `tests/integration/test_status_cli.py` — CLI integration tests

### Testing plan

Run `clasi status` against this repo. Use `click.testing.CliRunner` for
unit-style tests of flag parsing. Verify YAML output parses cleanly.

### Documentation updates

Update `clasi/cli.py` module docstring to add `clasi status` to the command list.
