---
id: "001"
title: "Add `exception` to ticket status enum and ticket_counts()"
status: done
use-cases:
  - SUC-001
  - SUC-002
  - SUC-007
depends-on: []
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add `exception` to ticket status enum and ticket_counts()

## Description

Two source files currently enumerate the valid ticket statuses and the
ticket count buckets. Both must be extended to include `exception`.

1. `clasi/tools/artifact_tools.py` line 601 — `valid_statuses` set inside
   `update_ticket_status()`. Add `"exception"` to the set.
2. `clasi/sprint.py` `ticket_counts()` (around line 411) — initialize a
   fourth bucket `"exception": 0` and handle `s == "exception"` in the loop.

These changes are foundational: the `throw_ticket_exception` MCP tool
(ticket 003) calls `update_ticket_status` internally and expects `exception`
to be valid.

## Acceptance Criteria

- [x] `update_ticket_status(path, "exception")` succeeds without raising
  `ValueError`.
- [x] `update_ticket_status(path, "invalid-value")` still raises `ValueError`.
- [x] `ticket_counts()` returns a dict with key `"exception"` initialized
  to `0` when no exception tickets exist.
- [x] `ticket_counts()` counts a ticket with `status: exception` in the
  `"exception"` bucket, not in `"open"` or anywhere else.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

**Files to modify**:
- `clasi/tools/artifact_tools.py` — extend `valid_statuses` set (1 line)
- `clasi/sprint.py` — extend `ticket_counts()` (2 lines)

**Approach**: Minimal additive change. In `artifact_tools.py`, change:
```python
valid_statuses = {"open", "in-progress", "done"}
```
to:
```python
valid_statuses = {"open", "in-progress", "done", "exception"}
```

In `sprint.py` `ticket_counts()`, change the counts initialization and add
the `"exception"` bucket handling analogous to the existing `"in_progress"`
case.

**Tests to write** (in ticket 008, but verify locally here):
- `test_update_ticket_status_accepts_exception`
- `test_update_ticket_status_rejects_unknown`
- `test_ticket_counts_includes_exception_bucket`

**Verification**: `uv run pytest tests/unit/test_artifact_tools.py tests/unit/test_sprint.py`
