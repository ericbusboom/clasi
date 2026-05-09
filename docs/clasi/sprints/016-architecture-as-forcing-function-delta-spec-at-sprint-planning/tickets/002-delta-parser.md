---
id: "016-002"
title: "Delta parser: parse and validate architecture-delta.md"
status: todo
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
depends-on: ["016-001"]
issue: delta-specs-for-brownfield-architecture-changes.md
---

# 016-002: Delta parser — parse and validate architecture-delta.md

## Description

Implement `clasi/delta/parse.py`. The parser takes a string of
`architecture-delta.md` content and returns an `ArchitectureDelta` or raises
`DeltaParseError` with a line number and rule name. This is a pure function
— no IO.

MODIFIED entries describe the change in prose. There is no requirement that
MODIFIED entries include "full updated content" — they describe what changed,
and the reviewer reads the prose. The parser does NOT enforce non-empty body
on MODIFIED items (empty body is still a signal worth rejecting, but the
standard is "non-empty prose," not "round-trippable replacement content").

## Acceptance Criteria

- [ ] `clasi/delta/parse.py` exports `parse(text: str) -> ArchitectureDelta`.
- [ ] The parser handles all four valid section headings:
  `### ADDED Components`, `### MODIFIED Components`,
  `### REMOVED Components`, `### RENAMED Components`,
  `### ADDED Scenarios`, `### MODIFIED Scenarios`,
  `### REMOVED Scenarios`, `### RENAMED Scenarios`.
- [ ] Items under `#### Component: <name>` and `#### Scenario: <name>` are
  collected into `DeltaItem` objects with the correct `kind` and `category`.
- [ ] RENAMED items parse `OldName → NewName`; `new_name` is set on the
  `DeltaItem`.
- [ ] Body text between item headings is captured as `DeltaItem.body`.
- [ ] MODIFIED items must have non-empty body (whitespace-only body raises
  `DeltaParseError`). The body is prose describing the change — no
  round-trippability requirement.
- [ ] The `## Specification` section, if present, is silently ignored with
  a warning printed to stderr (not a parse error).
- [ ] `parse()` is importable from `clasi.delta.parse`.
- [ ] All tests pass.

## Rejection Modes (must raise `DeltaParseError`)

- [ ] Item heading (`#### Component:` or `#### Scenario:`) appears outside
  any `### <KIND> <Category>` section.
- [ ] Section heading has an unrecognized KIND (e.g., `### CHANGED Components`).
- [ ] Section heading has an unrecognized Category.
- [ ] MODIFIED item has an empty body (only whitespace).
- [ ] RENAMED item is missing `→` in the name field.
- [ ] Duplicate item identity (same kind + category + name) within one delta.

## Implementation Plan

### Approach

Line-by-line state machine parser. Maintain current section state. On each
line, check if it matches a section heading or item heading pattern. Collect
item body lines until the next heading. At end of parse, validate accumulated
items.

### Files to Create/Modify

- `clasi/delta/parse.py` (create)
- `tests/unit/delta/test_parse.py` (create) — happy-path tests

### Testing Plan

- Parse a fully valid delta with all four kinds and both categories.
- Parse a delta with only ADDED Components.
- Parse a delta with a `## Specification` section (expect warning, no error).
- Verify returned `ArchitectureDelta.items` has correct count and fields.

### Documentation Updates

None for this ticket.
