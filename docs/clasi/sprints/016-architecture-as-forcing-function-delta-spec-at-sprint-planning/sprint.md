---
id: "016"
title: "Architecture as forcing-function delta spec at sprint planning"
status: planning
branch: sprint/016-architecture-as-forcing-function-delta-spec-at-sprint-planning
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004, SUC-005]
todos:
  - delta-specs-for-brownfield-architecture-changes.md
  - sprint-process-changes.md (architecture-positioning half only)
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016: Architecture as forcing-function delta spec at sprint planning

## Goals

Replace CLASI's free-prose `architecture-update.md` with a structured,
machine-parseable delta format authored at sprint planning time. Move the
architecture artifact to the front of sprint planning so it functions as
a structural contract — written before tickets exist — rather than a
post-hoc record.

## Problem

Two failure modes in the current brownfield model recur:

**Unverifiable changes.** A free-prose architecture-update can say "we
removed the FooBar service" with no parseable assertion of what "remove"
means structurally. The reviewer reads prose and guesses. The architecture
reviewer cannot automatically distinguish a well-formed plan from a vague
description.

**Wrong position.** The architecture update was written at sprint end as a
record of what changed. That position made it a recording artifact with no
forcing function. Tickets were designed without a prior structural contract;
the architect narrated what the coders had already decided.

## Solution

A combined solution from two source TODOs:

1. **Delta format** (from `delta-specs-for-brownfield-architecture-changes`):
   Replace free-prose `architecture-update.md` with a structured
   `architecture-delta.md` using ADDED / MODIFIED / REMOVED / RENAMED
   headings. Hard parse rules make every change assertion machine-checkable.

2. **Planning-time positioning** (from `sprint-process-changes`,
   architecture-positioning half only): Move the architecture delta to the
   front of sprint planning — between use cases and tickets. Tickets are
   derived from an already-written structural plan, not the reverse.

Together: the sprint planner authors a delta at planning time as the structural
contract; the validator rejects malformed deltas before review; the reviewer
evaluates a parseable artifact; the delta is archived as historical record when
the sprint closes.

## Design Decisions Baked In (not subject to re-litigation)

**Canonical design docs are frozen project-init artifacts.**
`docs/design/specification.md` and `docs/design/usecases.md` are authored
once at project initiation. Sprint close does NOT update them. Existing
projects keep theirs as-is — frozen historical record alongside the deltas.
"What is the architecture now?" is answered by reading the code, not by
reading a snapshot doc.

**Deltas accumulate as historical record.**
Per-sprint `architecture-delta.md` files live under
`docs/clasi/sprints/<id>/` and travel into `done/<id>/` at close.
The delta corpus plus the code is the architecture history.
No merge step exists. `Sprint.archive()` is not modified with merge logic.

**MODIFIED entries describe the change in prose.**
The "MODIFIED entries MUST include full updated content" rule is dropped.
MODIFIED items describe what changed and why — prose for human reviewers.
No round-trippability requirement. Non-empty body is still required (the
author must say something meaningful); whitespace-only body is a parse error.

**Validate-on-write hook stays.**
The PostToolUse hook validates `architecture-delta.md` on write. Format
errors caught at write-time keep review focused on content.

**Architecture-review is parser-first.**
The `architecture-review` skill runs the parser first — parse → validate →
if invalid, reject with clear error → if valid, do semantic review.

**Item identity: component names and scenario titles.**
Renaming requires a RENAMED entry. No per-item ID management.

**No `clasi/delta/merge.py`.** No close-sprint merge integration. No
feature flag.

## Success Criteria

- `clasi/delta/` package exists with `parse.py` and `model.py`; no `merge.py`.
- `clasi/schemas/se-process/delta-template.md` exists and is the skeleton
  sprint planners fill in.
- `clasi sprint validate-delta <id>` CLI subcommand exists and returns
  clear errors for every rejection mode.
- A PostToolUse hook validates `architecture-delta.md` on save, surfacing
  parse errors without blocking the write.
- The `architecture-authoring` skill's delta mode produces valid
  `architecture-delta.md` output; MODIFIED entries use prose, not full
  replacement content.
- The `architecture-review` skill runs the parser first; rejects on parse
  failure before semantic review.
- The sprint planner agent produces `architecture-delta.md` (not
  `architecture-update.md`) as part of Detail Mode planning.
- Documentation explicitly establishes: canonical design docs are frozen;
  deltas accumulate as historical record; code is the source of truth.
- All existing tests continue to pass.

## Scope

### In Scope

- `clasi/delta/` package: model, parser (no merger)
- Delta format spec as documented in the source TODO (minus merge semantics)
- `clasi/schemas/se-process/delta-template.md` (skeleton template)
- `clasi sprint validate-delta <id>` CLI subcommand
- PostToolUse hook for validate-on-write
- `architecture-authoring` skill: brownfield/delta mode update
- `architecture-review` skill: parser-first step
- `architecture-update.md` deprecation (plan-sprint and sprint-planner
  agent prompts updated)
- Phase-machine ordering: architecture-delta authored at planning, before
  tickets
- Tests for all parser rejection branches
- Integration test: validate + hook end-to-end (no merge)
- Documentation updates: SE overview, README, se-overview-template

### Out of Scope

- `clasi/delta/merge.py` — not built
- close-sprint merge step — close-sprint contract is UNCHANGED
- Feature flag — no merge, no flag needed
- Source-of-truth doc modification at sprint close — not done
- Specification-doc deltas (`## Specification` section in the delta) — v2
- Skills and rules as named delta categories — not planned
- 3-way merge for parallel sprints — deferred
- Diff viewer for delta vs code — manual git diff covers v1
- Backfill of historical `architecture-update.md` files to delta format
- Exception cord for lower-level agents (the other half of
  `sprint-process-changes`) — separate TODO

## Test Strategy

- **Unit tests** for `clasi/delta/parse.py`: valid documents, every
  rejection mode (missing section, wrong KIND, item outside section,
  MODIFIED with empty body, malformed RENAMED, duplicate identity).
- **Integration test**: end-to-end — write a delta, validate it via CLI,
  confirm hook fires, verify no source-of-truth docs are modified.
- Existing test suite must remain green throughout.

## Architecture Notes

Key design constraints:
- Parse is pure (no IO, no state). IO happens at call sites only.
- The delta format is the authoritative spec. The parser implements the
  format; the format does not drift from the parser.
- The plan-sprint agent prompt and sprint-planner agent prompt both refer
  to `architecture-delta.md`; `architecture-update.md` is removed from
  those prompts as a valid output name.
- `Sprint.archive()` is not modified with merge logic. The delta travels
  into `done/` intact by virtue of the directory move.

## Dependencies

- Sprint 015 (layout migration to `.clasi/`) must be done. This sprint
  references `.clasi/` paths throughout. Sprint 015 was merged to master
  before this sprint was created.
- No other blocking dependencies.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed (self-reviewed — APPROVE WITH CHANGES)
- [ ] Stakeholder has approved use cases (pending — this is the stopping point)

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Delta model: Pydantic types for ADDED/MODIFIED/REMOVED/RENAMED items | — |
| 002 | Delta parser: parse and validate architecture-delta.md | 001 |
| 004 | Parser rejection tests: all invalid-delta branches | 002 |
| 006 | Delta template: clasi/schemas/se-process/delta-template.md | 002 |
| 007 | CLI subcommand: clasi sprint validate-delta | 002 |
| 008 | PostToolUse hook: validate-on-write for architecture-delta.md | 002 |
| 009 | architecture-authoring skill: brownfield delta mode | 006 |
| 010 | architecture-review skill: parser-first step | 002 |
| 012 | Integration test: delta authoring, validate, and archive as historical record | 007, 008 |
| 014 | Phase-machine: sprint planner authors delta before tickets | 009, 010 |
| 015 | Documentation and deprecation: delta-as-historical-record model | 014 |

Tickets execute serially in the order listed.
