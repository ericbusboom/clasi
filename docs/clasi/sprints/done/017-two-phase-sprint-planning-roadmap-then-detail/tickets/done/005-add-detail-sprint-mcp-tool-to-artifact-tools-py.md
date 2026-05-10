---
id: '005'
title: Add detail_sprint MCP tool to artifact_tools.py
status: done
use-cases:
- SUC-002
depends-on:
- 017-004
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add detail_sprint MCP tool to artifact_tools.py

## Description

A new MCP tool `detail_sprint(sprint_id)` is registered in
`clasi/tools/artifact_tools.py`. It is a thin wrapper around
`Sprint.detail_promote()` (implemented in ticket 004).

The tool follows the same pattern as other single-sprint tools in that file
(e.g., `advance_sprint_phase`, `close_sprint`): resolve sprint by ID, call
domain method, return JSON result.

**Files to modify:**
- `clasi/tools/artifact_tools.py`: add `@server.tool()` function `detail_sprint`.

## Acceptance Criteria

- [x] `@server.tool()` named `detail_sprint` is registered and callable via MCP.
- [x] Accepts `sprint_id: str`.
- [x] Delegates to `sprint.detail_promote()` and returns JSON with `{sprint_id, phase, files_written}`.
- [x] On `ValueError` from `detail_promote()`, returns a JSON error string with a clear message (no unhandled exception).
- [x] `get_sprint_phase(sprint_id)` after a successful call returns `{"phase": "planning-docs"}`.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

- In `clasi/tools/artifact_tools.py`, add after the `create_sprint` tool:

```python
@server.tool()
def detail_sprint(sprint_id: str) -> str:
    """Promote a roadmap sprint to detail planning.

    Scaffolds usecases.md, architecture-update.md, tickets/, and tickets/done/
    for the given sprint and advances the state DB phase from roadmap to
    planning-docs.

    Args:
        sprint_id: The sprint ID (e.g., '017')

    Returns JSON with {sprint_id, phase, files_written}.
    """
    try:
        project = get_project()
        sprint = project.get_sprint(sprint_id)
        result = sprint.detail_promote()
        return json.dumps(result)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})
```

- No imports needed beyond what is already present (`json`, `get_project`).

## Testing

- **Existing tests to run**: `uv run pytest tests/system/test_artifact_tools.py`, `uv run pytest`
- **New tests to write**: Covered in ticket 010.
- **Verification command**: `uv run pytest`
