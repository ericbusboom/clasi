---
id: 008
title: Write tests for exception throw, status transition, routing, and SE overview
  section
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-007
depends-on:
- 018-001
- 018-002
- 018-003
- 018-007
github-issue: ''
todo: ''
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Write tests for exception throw, status transition, routing, and SE overview section

## Description

Write all tests for the exception protocol changes implemented in tickets
001–007. Also add the SE overview "Exception protocol" section to
`clasi/se-overview-template.md`, and write a test that confirms the section
exists (so it doesn't silently drift out of the template in the future).

This is the final ticket in the sprint. All code changes are complete when
this ticket is done.

## Acceptance Criteria

### Unit tests — `tests/unit/test_artifact_tools.py`
- [x] `test_update_ticket_status_accepts_exception`: `update_ticket_status`
  with `status="exception"` succeeds and writes `exception` to frontmatter.
- [x] `test_update_ticket_status_rejects_unknown_still`: unknown status still
  raises `ValueError` after adding `exception`.
- [x] `test_throw_ticket_exception_writes_frontmatter`: calling
  `throw_ticket_exception` writes all five fields of the `exception:` block
  to the ticket frontmatter.
- [x] `test_throw_ticket_exception_sets_status_exception`: after calling
  the tool, ticket `status` field is `"exception"`.
- [x] `test_throw_ticket_exception_returns_thrown_at`: return JSON contains
  `thrown_at` as an ISO-8601 string.
- [x] `test_throw_ticket_exception_invalid_thrown_by`: `ValueError` / JSON
  error on invalid `thrown_by`.
- [x] `test_throw_ticket_exception_invalid_surface`: `ValueError` / JSON
  error on invalid `surface`.
- [x] `test_throw_ticket_exception_unknown_path`: error on non-existent path.

### Unit tests — `tests/unit/test_sprint.py`
- [x] `test_ticket_counts_includes_exception_bucket`: `ticket_counts()`
  returns `{"open": 0, "in_progress": 0, "done": 0, "exception": 1}` when
  one ticket has `status: exception`.

### Unit tests — `tests/unit/test_ticket.py`
- [x] `test_exception_payload_absent`: `Ticket.exception_payload` returns
  `None` when no `exception` key in frontmatter.
- [x] `test_exception_payload_present`: returns dict with all fields when
  `exception:` block is present.

### System tests — `tests/system/test_exception_flow.py` (new file)
- [x] `test_throw_and_list`: create a sprint + ticket, call
  `throw_ticket_exception`, assert `list_tickets(status="exception")`
  returns that ticket.
- [x] `test_exception_ticket_blocks_pre_close`: assert
  `review_sprint_pre_close` returns an error (not success) when a ticket
  with `status: exception` exists in the sprint.

### SE overview update
- [x] `clasi/se-overview-template.md` gains an "Exception protocol" section
  covering: threshold, payload schema, ticket as carrier, team-lead routing
  branches, revision naming convention, and calibration signal.

### Test for SE overview
- [x] `tests/docs/test_se_overview.py` (new file or existing expanded):
  `test_exception_protocol_section_exists` — assert `se-overview-template.md`
  contains the substring `"Exception protocol"` (or the heading text used).

### Regression
- [x] `uv run pytest` passes with no regressions across all existing tests.

## Implementation Plan

**New files**:
- `tests/system/test_exception_flow.py`
- `tests/docs/test_se_overview.py` (or add to existing docs test if present)

**Modified files**:
- `tests/unit/test_artifact_tools.py` — add exception-related test functions
- `tests/unit/test_sprint.py` — add `test_ticket_counts_includes_exception_bucket`
- `tests/unit/test_ticket.py` — add `test_exception_payload_*` tests
- `clasi/se-overview-template.md` — add "Exception protocol" section

**Approach**: Follow patterns in existing unit tests. For system tests, use
the existing pattern of creating a temporary project directory with a sprint
and tickets. For the SE overview update, insert the new section after the
existing "Architecture" or "Sprint planning" section, whichever is closest
in topic.

**Verification**: `uv run pytest` — all tests pass.
