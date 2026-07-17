---
id: '003'
title: 'Design doc store: clasi.design.store module'
status: open
use-cases: [SUC-001, SUC-002]
depends-on: ['002']
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Design doc store: clasi.design.store module

## Description

Implement `clasi.design.store`, the module that reads and writes the
persistent `docs/design/` doc set (`design.md`, per-subsystem docs, and
subsystem `README.md` frontmatter) as `Artifact` objects (reusing
`src/clasi/artifact.py` and `src/clasi/frontmatter.py` — do not
reimplement frontmatter parsing). This module knows the *shape* of a
design doc and a subsystem README (what frontmatter fields they carry)
but does not validate cross-doc consistency (that's ticket 004) and does
not touch git (that's ticket 005).

Design doc frontmatter references its source path(s) and README, per the
issue. Subsystem README frontmatter references its design doc, plus a
subsystem name and one-line description.

## Acceptance Criteria

- [ ] A function/class to read the canonical doc set given a `Project`:
      enumerates expected design docs and READMEs via `clasi.design.paths`
      + `Project.sources`, and returns `Artifact` handles (not
      necessarily requiring they exist yet — existence checking is the
      validator's job).
- [ ] A function to write a design doc: given a subsystem path and
      content, writes `docs/design/<slug>.md` with frontmatter containing
      at minimum the source path(s) and the README path.
- [ ] A function to write a subsystem README: given a subsystem path,
      name, one-line description, and design-doc reference, writes
      `<subsystem>/README.md` with the required frontmatter fields.
- [ ] A function to write the top-level `design.md` (system document).
- [ ] Frontmatter round-trips: writing then reading a design doc or
      README returns the same structured fields (uses `Artifact.write`/
      `Artifact.frontmatter`, matching the existing round-trip guarantee
      `frontmatter.py` already provides — see its test coverage as the
      pattern to match).
- [ ] Does not overwrite an existing README's non-frontmatter body content
      unless explicitly told to (bootstrap creates fresh; later
      re-bootstrap or hand-edits should not be silently destroyed) — at
      minimum, document this module's overwrite semantics clearly even if
      full merge logic is out of scope.

## Implementation Plan

**Approach**: Thin wrapper over `Artifact` (`src/clasi/artifact.py`)
specialized to the two document shapes (design doc, subsystem README).
Mirrors how other artifact kinds (issues, tickets, sprints) already wrap
`Artifact` elsewhere in the codebase — look at `src/clasi/issue.py` or
`src/clasi/ticket.py` for the established wrapper pattern before writing
a new one from scratch.

**Files to create/modify**:
- `src/clasi/design/store.py` (new)

**Testing plan**:
- Unit tests: write-then-read round-trip for design doc, README, and
  `design.md`; frontmatter field presence and correctness; enumeration
  of expected doc set given a `Project` fixture with a declared
  `sources:` list (single- and multi-root fixtures).
- Use a temp-directory `Project` fixture (check `tests/` for an existing
  fixture pattern — likely present given the breadth of existing
  sprint/ticket/issue tests) rather than mutating this repo's own
  `docs/design/`.

**Documentation updates**:
- Docstrings describing the frontmatter contract for each doc kind — this
  is the reference the bootstrap skill (ticket 007) and validator
  (ticket 004) both depend on being accurate.
