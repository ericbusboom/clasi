---
id: '004'
title: Inconsistency detection for declared vs computed state drift
status: done
use-cases:
- SUC-007
depends-on:
- '002'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Inconsistency detection for declared vs computed state drift

## Description

The issue requires that `clasi status` detect when an artifact's frontmatter
`status:` field disagrees with the state machine's computed state. These
discrepancies appear in the `inconsistencies:` list in the output.

This ticket implements `clasi/status/inconsistency.py` with
`detect_inconsistencies(project, status_dict) -> list[dict]`. It reads each
sprint's `sprint.md` `status:` frontmatter and each ticket's `status:`
frontmatter, then compares against the `state:` values already computed in
`status_dict`. Any mismatch becomes a `state_drift` entry.

## Acceptance Criteria

- [x] `clasi/status/inconsistency.py` defines `detect_inconsistencies(project, status_dict) -> list[dict]`.
- [x] For each sprint in `status_dict["sprints"]`, compares sprint.md `status:` frontmatter against `state:` in the dict.
- [x] For each ticket in `tickets.details`, compares ticket frontmatter `status:` against `state:` in the dict.
- [x] Any mismatch produces an entry: `{kind: "state_drift", machine: "sprint"|"ticket", id: ..., declared: ..., computed: ..., explanation: ...}`.
- [x] `explanation:` names the specific predicates that would need to be true for the declared state to be valid (using `inspect_transitions` or `evaluate_predicates`).
- [x] Consistent artifacts produce an empty list.
- [x] `reporter.py` calls `detect_inconsistencies` and merges the result into `status_dict["inconsistencies"]` (replacing the empty stub list from ticket 002).
- [x] Unit tests in `tests/unit/test_status/test_inconsistency.py` cover:
  - Sprint with matching declared/computed state → empty list.
  - Sprint with mismatched declared/computed state → one `state_drift` entry.
  - Ticket with mismatched state → one `state_drift` entry.
- [x] `uv run pytest tests/unit/test_status/` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### Approach

`detect_inconsistencies(project, status_dict)` iterates the sprints and tickets
already present in `status_dict`. For each:

1. Read the artifact's frontmatter `status:` via `clasi.frontmatter.read_frontmatter`.
2. Compare against the `state:` key already in the dict entry.
3. If they differ, call `evaluate_predicates` on all predicates for the
   declared state's invariants to produce the explanation.

The comparison is string-based. If `status:` is missing from frontmatter, skip
that artifact (no declared state to compare against).

Wire into `reporter.py`: after building the full dict, call
`detect_inconsistencies(project, full_dict)` and assign the result to
`full_dict["inconsistencies"]`.

### Files to create

- `clasi/status/inconsistency.py` — `detect_inconsistencies`
- `tests/unit/test_status/test_inconsistency.py` — unit tests

### Files to modify

- `clasi/status/reporter.py` — call `detect_inconsistencies` and merge result

### Testing plan

Create minimal sprint/ticket dicts with known `state:` values. Provide matching
and mismatching frontmatter. Verify output structure and that the explanation
references real predicate names.

### Documentation updates

Docstring describing the `state_drift` entry format.
