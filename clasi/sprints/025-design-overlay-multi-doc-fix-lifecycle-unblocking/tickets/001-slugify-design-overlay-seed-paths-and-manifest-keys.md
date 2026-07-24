---
id: '001'
title: Slugify design-overlay seed paths and manifest keys
status: in-progress
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Slugify design-overlay seed paths and manifest keys

## Description

Foundation ticket for the primary issue. Today `seed_sprint_design_overlay`
(`src/clasi/tools/artifact_tools.py` ~L286-334) hardcodes
`project.design_dir / name` as its path-resolution base — unreachable
for co-located subsystem docs without a `../../` escape — and
`seed_and_commit` (`src/clasi/design/overlay.py` ~L183-245) writes each
seeded file to `sprint_design_dir / canonical_path.name` and keys the
`_sources.json` manifest by that same bare basename. Two co-located
`DESIGN.md` docs seeded in the same call silently collide: the second
`shutil.copyfile` overwrites the first file, and the second manifest
write clobbers the first entry (last write wins).

This ticket makes `seed_sprint_design_overlay` accept co-located
canonical source paths directly, derives a unique, stable, reversible
slug per doc, and changes `seed_and_commit` to write under and key by
that slug instead of `canonical_path.name`. This is the foundation every
other design-overlay ticket in this sprint builds on.

**Slug transform** (resolves Open Question 1 in sprint.md's Architecture
section): derive the slug from the canonical path's components relative
to the nearest enclosing source root (or `docs/design/` for the
system-level doc), joining directory segments with `-` and keeping the
final `DESIGN.md`/`design.md` filename, e.g.
`src/firm/app/DESIGN.md` under source root `src` to `firm-app-DESIGN.md`;
`docs/design/design.md` (system doc, no source-root prefix) to
`design.md` unchanged (already unique). Document the exact transform in
the function's docstring so it is not re-derived ad hoc by callers.
Re-seeding the same canonical doc must reproduce the same slug (stable
across calls), so a re-seed overwrites its own prior copy rather than
accumulating a duplicate under a different name.

## Acceptance Criteria

- [x] `seed_sprint_design_overlay`'s `doc_names` accepts co-located
      canonical source paths (e.g. `src/firm/app/DESIGN.md`) with no
      `../../` escape required, in addition to system-doc-relative names
      it already accepts.
- [x] The function's docstring no longer claims `doc_names` are
      "relative to `docs/design/`" and instead documents the accepted
      forms and the slug transform.
- [x] `seed_and_commit` writes each seeded file under its derived slug
      (not `canonical_path.name`) and records the slug as the
      `_sources.json` manifest key.
- [x] Seeding two co-located `DESIGN.md` docs (different subsystems) in
      one `seed_sprint_design_overlay` call produces two distinct files
      on disk and two distinct manifest entries — neither the file nor
      the manifest entry from the first doc is overwritten by the
      second.
- [x] Re-seeding the same doc (same canonical path) a second time
      reproduces the same slug (idempotent naming, not a new duplicate).
- [x] Existing single-doc overlay behavior is unchanged in outcome for
      any doc whose derived slug does not collide with anything (the
      common case) — no regression for sprints already relying on
      single-doc seeding.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "overlay or artifact_tools or design"`
- **New tests to write**: unit tests for the slug-derivation function
  covering: a co-located subsystem doc, the system-level doc, and a
  re-seed producing the same slug. Unit test for `seed_and_commit`
  seeding two same-basename docs in one call and asserting both files
  and both manifest entries exist and are distinct. (Ticket 003 covers
  the full end-to-end multi-doc lifecycle regression test; this
  ticket's tests are unit-scoped to the slug/seed mechanics themselves.)
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
