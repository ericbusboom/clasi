---
id: "010"
title: "Write system tests for detail_sprint MCP tool and list_sprints roadmap filter"
status: done
use-cases:
  - SUC-006
depends-on:
  - 017-005
  - 017-006
  - 017-009
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Write system tests for detail_sprint MCP tool and list_sprints roadmap filter

## Description

System/integration tests covering the MCP tool layer (tickets 005-006). These
tests call the tool functions directly or via a test MCP client, exercising
the full stack including the state DB.

**Files to create or extend:**
- `tests/system/test_artifact_tools.py` (extend existing or create)

## Acceptance Criteria

- [x] `test_detail_sprint_tool_roundtrip`: calls `create_sprint` (asserts phase = `roadmap`), then `detail_sprint`, then `get_sprint_phase` (asserts phase = `planning-docs`), then asserts all three artifact files exist.
- [x] `test_detail_sprint_rejects_non_roadmap`: calls `detail_sprint` on a sprint already in `planning-docs`; asserts the response contains an `"error"` key with a non-empty message.
- [x] `test_list_sprints_status_roadmap`: creates two sprints, advances one to `planning-docs` via `detail_sprint`, calls `list_sprints(status="roadmap")`, asserts only the non-advanced sprint is returned.
- [x] `test_list_sprints_default_returns_all`: same setup; calls `list_sprints()` (no filter), asserts both sprints appear.
- [x] All tests pass: `uv run pytest tests/system/`.
- [x] Full suite passes: `uv run pytest`.

## Implementation Plan

- Locate `tests/system/test_artifact_tools.py` and read the existing fixture setup.
- Add the four tests described above using the same fixture pattern.
- Each test creates a temporary project directory with a fresh state DB.

## Testing

- **Existing tests to run**: `uv run pytest tests/system/`
- **New tests to write**: All described in acceptance criteria.
- **Verification command**: `uv run pytest`
