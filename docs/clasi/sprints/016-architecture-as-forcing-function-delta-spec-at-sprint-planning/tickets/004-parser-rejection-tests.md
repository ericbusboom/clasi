---
id: "016-004"
title: "Parser rejection tests: all invalid-delta branches"
status: todo
use-cases: [SUC-002, SUC-003]
depends-on: ["016-002"]
---

# 016-004: Parser rejection tests — all invalid-delta branches

## Description

Write exhaustive tests for every `DeltaParseError` rejection mode. Every
rejection branch documented in the architecture must have a test. This ticket
is pure tests — no new production code.

## Acceptance Criteria

- [ ] `tests/unit/delta/test_invalid_deltas.py` exists.
- [ ] One test per rejection mode:
  - [ ] Item heading outside any section: `#### Component: Foo` with no preceding
    `### ADDED Components` or similar.
  - [ ] Unknown KIND in section heading: `### CHANGED Components`.
  - [ ] Unknown Category in section heading: `### ADDED Rules`.
  - [ ] MODIFIED item with empty body (only whitespace after the heading).
  - [ ] RENAMED item missing `→` (e.g., `#### Component: Foo to Bar`).
  - [ ] Duplicate item identity: two `#### Component: Foo` under `### ADDED Components`.
- [ ] Each test asserts:
  - `DeltaParseError` is raised.
  - `error.line` is the correct line number.
  - `error.rule` is a non-empty string identifying the violated rule.
  - `error.message` is human-readable.
- [ ] All tests pass.

## Implementation Plan

### Approach

Parametrize the test with inline fixture strings, one per rejection mode. No
fixture files needed. Assert on the exception fields.

### Files to Create/Modify

- `tests/unit/delta/test_invalid_deltas.py` (create)

### Testing Plan

The tests ARE the deliverable. Run with `uv run pytest tests/unit/delta/test_invalid_deltas.py`.

### Documentation Updates

None.
