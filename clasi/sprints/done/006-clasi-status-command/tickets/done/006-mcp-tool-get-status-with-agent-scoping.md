---
id: '006'
title: 'MCP tool: get_status with agent scoping'
status: done
use-cases:
- SUC-006
depends-on:
- '003'
- '004'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# MCP tool: get_status with agent scoping

## Description

This ticket adds `get_status` as an MCP tool in `clasi/tools/process_tools.py`.
It wraps `build_status` and `narrow_status` and returns the result as JSON —
the same shape as the CLI but returned as a structured MCP tool response rather
than printed to stdout.

## Acceptance Criteria

- [x] `get_status` is registered as an `@server.tool()` in `process_tools.py`.
- [x] Signature: `get_status(agent: str = "team-lead", sprint_id: str | None = None, ticket_id: str | None = None) -> str` (JSON string).
- [x] Agent defaults to `$CLASI_AGENT_NAME` env var if `agent` not specified, then `"team-lead"`.
- [x] Returns the same shape as `clasi status --format json`.
- [x] `get_status(agent="sprint-planner", sprint_id="006")` returns narrowed sprint-planner JSON.
- [x] `get_status(agent="programmer", ticket_id="006-003")` returns narrowed programmer JSON.
- [x] If project is not CLASI-initialized, returns a JSON error object `{"error": "not a CLASI project"}`.
- [x] Integration test in `tests/integration/test_status_mcp.py` verifies the tool return shape.
- [x] `uv run pytest tests/integration/test_status_mcp.py` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### Approach

Add to `process_tools.py`:

```python
@server.tool()
def get_status(agent: str = "team-lead", sprint_id: str | None = None, ticket_id: str | None = None) -> str:
    from clasi.status import build_status, narrow_status
    from clasi.status.formatting import to_json
    project = get_project()
    resolved_agent = agent or os.environ.get("CLASI_AGENT_NAME") or "team-lead"
    full = build_status(project, agent=resolved_agent, sprint_id=sprint_id, ticket_id=ticket_id)
    narrowed = narrow_status(full, agent=resolved_agent, sprint_id=sprint_id, ticket_id=ticket_id)
    return to_json(narrowed)
```

Wrap in try/except to return error JSON on unexpected failures.

### Files to modify

- `clasi/tools/process_tools.py` — add `get_status` tool

### Files to create

- `tests/integration/test_status_mcp.py` — MCP tool integration tests

### Testing plan

Call `get_status()` directly (not via HTTP) in tests. Verify `json.loads`
succeeds and top-level keys match the expected shape.

### Documentation updates

Add `get_status` to any tool listing in the MCP server docstring.
