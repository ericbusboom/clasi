---
id: '016'
title: 'Architecture-update positioning: prose planning artifact, documented'
status: done
branch: sprint/016-architecture-as-forcing-function-delta-spec-at-sprint-planning
use-cases:
- SUC-001
- SUC-002
todos:
- sprint-process-changes.md (architecture-positioning half only)
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016: Architecture-update positioning — prose planning artifact, documented

## Goals

Fix documentation and skill prose so that `architecture-update.md` is
unambiguously described as a prose planning artifact authored *before* tickets
exist, serving as the structural forcing function that tickets are derived from.
Accumulated per-sprint, these files are the ADR history of the project.

## Problem

Three independent code/doc reads confirm the following:

- **Phase machine is already correct.** `state_db_class.py` has
  `planning-docs → architecture-review → stakeholder-review → ticketing →
  executing → closing → done` — gates are in place, nothing to change.
- **Sprint-planner agent is already correct.** Phase 2 writes
  `architecture-update.md`; Phase 3 does the inline architecture self-review;
  Phase 4 creates tickets. The ordering is right and no stakeholder gate is
  inserted before tickets (matching the locked-in decision).
- **architecture-review skill is already clean.** No parser, no format check,
  no validate-delta reference — purely prose-and-content review.

What remains is a narrow documentation/framing problem:

1. `architecture-authoring/SKILL.md` Mode 2 opens with "Write a focused
   architecture diff describing *what changed* in this sprint." The phrase
   "what changed" sounds retrospective. No explicit statement that the
   artifact is written before tickets exist, or that its purpose is "describe
   the change clearly enough that tickets can be derived from it."

2. `software-engineering.md` Architecture artifact section (§2) describes
   "versioned architecture documents… each version represents the target state
   *after* a sprint completes" — which implies a merge/consolidation step that
   does not exist. The per-sprint `architecture-update.md` model is not
   explained there.

3. `se-overview-template.md` and `README.md` do not describe when
   `architecture-update.md` is authored or its role as historical record. Minor
   omissions, not wrong.

## Solution

Two targeted documentation changes cover the genuine remaining work:

1. **`architecture-authoring/SKILL.md`** — Fix Mode 2 opening framing from
   retrospective ("what changed") to forward-looking ("describe the
   architectural change clearly enough that tickets can be derived from it,
   before tickets exist"). One short paragraph edit.

2. **`software-engineering.md`, `se-overview-template.md`, `README.md`** —
   Add explicit language: architecture-update is authored at the front of sprint
   planning as a structural plan; per-sprint architecture-updates accumulate as
   ADRs at sprint granularity; canonical design docs are frozen project-init
   artifacts; code is the source of truth for current architecture.

## Design Decisions Baked In (not subject to re-litigation)

**Architecture-update is free prose.**
No structured delta format. No parser. No validator. No CLI subcommand.

**Phase machine is unchanged.**
`state_db_class.py` is not touched. The phase order is already correct.

**Sprint-planner agent prompt is unchanged at the structural level.**
It already does architecture before tickets, with inline review.

**No stakeholder gate before tickets.**
The only stakeholder-review gate is between `architecture-review` and
`ticketing` — the existing one. No new gate is added.

**Architecture-update accumulates as historical record.**
Per-sprint files live under `docs/clasi/sprints/<id>/` and travel to
`done/<id>/` at close. No merge step. Code is the source of truth.

## Success Criteria

- `architecture-authoring/SKILL.md` Mode 2 framing is forward-looking:
  "describe the architectural change clearly enough that tickets can be
  derived from it." Written before tickets exist.
- `software-engineering.md` correctly describes per-sprint
  `architecture-update.md` as a planning-time artifact that accumulates
  as historical record, not as a versioned snapshot updated at sprint close.
- `se-overview-template.md` and `README.md` are consistent with the above.
- No documentation file states that `architecture-update.md` is written at
  sprint close or as a retrospective record.
- No new code, tests, or phase-machine changes are introduced.

## Scope

### In Scope

- `architecture-authoring/SKILL.md`: Fix Mode 2 framing to forward-looking
  prose planning artifact
- `software-engineering.md`: Fix Architecture artifact section; describe
  per-sprint accumulation model
- `se-overview-template.md`: Add architecture-update positioning sentence
- `README.md`: Add/fix architecture-update description to match

### Out of Scope

- `clasi/state_db_class.py` — not touched (already correct)
- Sprint-planner agent prompt — not touched at structural level (already correct)
- `architecture-review/SKILL.md` — already clean (no parser, no format check)
- `clasi/delta/` package — not built
- Parser, validator, CLI subcommand — not built
- Template rewrite — template stays as-is
- Merge step at sprint close — not done
- Exception cord for lower-level agents — separate TODO

## Test Strategy

Documentation-only changes. No automated tests needed. Manual verification:
confirm no file states the architecture-update is written retrospectively or
at sprint close.

## Architecture Notes

No code changes. All changes are prose documentation updates. The artifact
model is unchanged; only its description in documentation is corrected.

## Dependencies

- Sprint 015 (layout migration to `.clasi/`) must be done. Sprint 015 was
  merged to master before this sprint was created.
- No other blocking dependencies.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed (self-reviewed)
- [ ] Stakeholder has approved use cases (pending — this is the stopping point)

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 002 | architecture-authoring skill: forward-looking prose framing | — |
| 004 | Documentation: ADRs-at-sprint-granularity and planning-time positioning | 002 |

Tickets execute serially in the order listed.
