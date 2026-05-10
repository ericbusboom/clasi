---
id: "006"
title: "Verify list_sprints status filter wiring in MCP tool layer"
status: todo
use-cases:
  - SUC-003
depends-on:
  - 017-003
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify list_sprints status filter wiring in MCP tool layer

## Description

`Project.list_sprints(status=None)` already supports status filtering in the
domain layer. The MCP tool `list_sprints` in `clasi/tools/artifact_tools.py`
must accept and pass through the `status` argument.

This ticket verifies the wiring is complete. If the MCP tool's signature does
not include a `status` parameter, add it. If the parameter exists but is not
forwarded to `project.list_sprints(status=...)`, fix the call.

**Files to modify (if needed):**
- `clasi/tools/artifact_tools.py`: ensure `list_sprints` MCP tool has
  `status: Optional[str] = None` parameter and passes it to `project.list_sprints(status)`.

## Acceptance Criteria

- [ ] `list_sprints` MCP tool accepts an optional `status` parameter.
- [ ] Calling `list_sprints(status="roadmap")` returns only sprints whose `sprint.md` has `status: roadmap`.
- [ ] Calling `list_sprints()` (no argument) returns all sprints regardless of status.
- [ ] `uv run pytest` passes with no regressions.

## Implementation Plan

- Read the `list_sprints` tool definition in `clasi/tools/artifact_tools.py`.
- If `status` parameter is missing, add `status: Optional[str] = None` to the signature.
- If `project.list_sprints()` call doesn't pass `status`, change it to `project.list_sprints(status=status)`.
- If already wired correctly, this ticket is a no-op except for adding a test note.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: Covered in ticket 010 (`test_list_sprints_status_roadmap`).
- **Verification command**: `uv run pytest`
