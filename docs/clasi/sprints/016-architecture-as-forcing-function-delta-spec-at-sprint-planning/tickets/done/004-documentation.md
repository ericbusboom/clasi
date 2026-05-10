---
id: 016-004
title: 'Documentation: ADRs-at-sprint-granularity and planning-time positioning'
status: done
use-cases:
- SUC-002
depends-on:
- 016-002
todos:
- sprint-process-changes.md
---

# 016-004: Documentation — ADRs-at-sprint-granularity and planning-time positioning

## Description

Update `software-engineering.md`, `se-overview-template.md`, and `README.md`
to correctly describe the `architecture-update.md` model: authored at the front
of sprint planning before tickets exist, accumulated as ADRs at sprint
granularity, never merged into canonical design docs.

**Verification findings per file**:

**`software-engineering.md`** — This needs the most substantive change.
The Architecture artifact section (§2) currently describes "versioned
architecture documents" in `.clasi/architecture/` and says "each version
represents the target state after a sprint completes." This describes the
*consolidated* architecture model produced by the `consolidate-architecture`
skill — a separate, optional artifact. The section sits adjacent to the sprint
directory layout that includes `architecture-update.md`, implying that the
per-sprint update feeds into the consolidated docs at sprint close. A
clarification paragraph is needed: per-sprint `architecture-update.md` files
are planning-time artifacts that accumulate as historical record. The sprint
lifecycle section (step 4) already correctly says "Architecture review: validate
the plan against the existing codebase" — which is the right ordering. No change
needed there.

**`se-overview-template.md`** — Sprint Detail Planning step mentions
"usecases, architecture, tickets" as a flat list. Add one sentence: the
architecture-update is authored before tickets and the per-sprint files
accumulate as historical record. The rest of the template is clean.

**`README.md`** — Sprint Planning section says "each sprint gets… an
Architecture document — components, design decisions, sprint changes." The
ordering is fine (architecture listed before code execution). Add one short
phrase: "authored before tickets are created and archived as historical record
at sprint close." That is the only addition needed.

## Acceptance Criteria

- [x] `software-engineering.md` Architecture artifact section (§2) is updated to:
  - Distinguish per-sprint `architecture-update.md` (planning-time, accumulates
    as historical record) from the consolidated architecture in
    `.clasi/architecture/` (optional, produced by `consolidate-architecture`
    skill).
  - NOT imply a merge step or snapshot update at sprint close for the
    per-sprint file.
  - State that code is the source of truth for current architecture. The
    per-sprint updates are the chronological record of structural intent.
  - State that canonical design docs (`design/overview.md`, etc.) are
    project-init artifacts, frozen after initiation.
- [x] `se-overview-template.md` Sprint Detail Planning step includes a sentence
  noting that `architecture-update.md` is authored before tickets and
  accumulates as historical record.
- [x] `README.md` Sprint Planning description includes the phrase "authored
  before tickets are created" in its description of the architecture document.
- [x] No documentation file states `architecture-update.md` is written at
  sprint close or as a retrospective record.
- [x] `Sprint.archive()` behavior is verified (read-only): confirm no explicit
  exclusion of `architecture-update.md` in `clasi/sprint.py`. No code change
  expected — the file travels to done/ via directory move.
- [x] All existing tests pass (`uv run pytest`).

## Implementation Plan

### Approach

1. Read `clasi/plugin/instructions/software-engineering.md` §2 (Architecture
   artifact section). Edit the section to add the clarification paragraph
   distinguishing per-sprint `architecture-update.md` from consolidated docs.
2. Read `clasi/se-overview-template.md` Sprint Detail Planning step. Add one
   sentence about authoring before tickets and historical accumulation.
3. Read `README.md` Sprint Planning section. Add the "authored before tickets"
   phrase to the architecture document bullet.
4. Read `clasi/sprint.py` — verify `archive()` moves the sprint directory
   intact. No code change expected.
5. Run `uv run pytest` to confirm no regressions.

### Files to Modify

- `clasi/plugin/instructions/software-engineering.md` (Architecture §2)
- `clasi/se-overview-template.md` (Sprint Detail Planning step)
- `README.md` (Sprint Planning section)

### Files to Read (verify only, no changes expected)

- `clasi/sprint.py` — `archive()` method

### Testing Plan

Run `uv run pytest`. No new tests required for documentation changes.

### Documentation Updates

This ticket IS the documentation update.
