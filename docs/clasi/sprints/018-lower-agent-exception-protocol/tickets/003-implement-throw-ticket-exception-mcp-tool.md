---
id: "003"
title: "Implement `throw_ticket_exception` MCP tool"
status: todo
use-cases:
  - SUC-007
  - SUC-001
  - SUC-002
depends-on:
  - "018-001"
  - "018-002"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement `throw_ticket_exception` MCP tool

## Description

Add a new `@server.tool()` function `throw_ticket_exception` to
`clasi/tools/artifact_tools.py`. This tool is the single atomic operation
for throwing an exception: it writes the `exception:` YAML block to the
ticket's frontmatter and sets the ticket status to `exception` in one call.

Interface:
```python
throw_ticket_exception(
    path: str,
    thrown_by: str,    # "programmer" | "sprint-planner"
    attempted: str,    # what was tried before hitting the wall
    conflict: str,     # the upstream decision that is blocked
    surface: str,      # "user-visible" | "internal"
) -> str  (JSON)
```

Depends on ticket 001 (`exception` in valid_statuses) and ticket 002
(`Ticket.exception_payload` property and schema definition).

## Acceptance Criteria

- [ ] `throw_ticket_exception` is registered as an MCP tool and callable via
  the MCP server.
- [ ] Calling the tool writes `exception:` block (all five fields including
  `thrown_at` as current UTC ISO-8601) to ticket frontmatter.
- [ ] Calling the tool sets ticket `status` to `exception`.
- [ ] Both payload write and status change occur; partial writes do not occur
  (write payload first, then status — if frontmatter write succeeds,
  status write follows immediately in same function).
- [ ] `thrown_by` validated against `{"programmer", "sprint-planner"}`; returns
  JSON error on invalid value.
- [ ] `surface` validated against `{"user-visible", "internal"}`; returns JSON
  error on invalid value.
- [ ] On unknown ticket path, returns JSON error with clear message.
- [ ] Returns JSON: `{path, old_status, new_status: "exception", thrown_at}`.
- [ ] `uv run pytest` passes with no regressions.

## Implementation Plan

**File to modify**: `clasi/tools/artifact_tools.py` — add new `@server.tool()`
function after `update_ticket_status`.

**Approach**:
1. Resolve ticket path via `resolve_artifact_path(path)`.
2. Validate `thrown_by` and `surface`.
3. Build `thrown_at = datetime.now(timezone.utc).isoformat()`.
4. Read current `old_status` from `Artifact(ticket_path).frontmatter`.
5. Write `exception:` block using `artifact.update_frontmatter(exception={...})`.
6. Write `status: exception` using `artifact.update_frontmatter(status="exception")`.
7. Return JSON `{path, old_status, new_status, thrown_at}`.

Both `update_frontmatter` calls are sequential in-process writes to the same
file — if the process crashes between them, the file may have the exception
block but still show the old status. This is acceptable: the presence of the
exception block is the meaningful signal; status is derivative.

**Tests** (written in ticket 008):
- `test_throw_ticket_exception_writes_frontmatter`
- `test_throw_ticket_exception_invalid_thrown_by`
- `test_throw_ticket_exception_invalid_surface`
- `test_throw_and_list` (system test)

**Verification**: `uv run pytest tests/unit/test_artifact_tools.py`
