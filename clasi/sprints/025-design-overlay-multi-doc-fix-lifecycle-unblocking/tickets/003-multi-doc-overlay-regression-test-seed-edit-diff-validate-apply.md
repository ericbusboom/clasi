---
id: '003'
title: Multi-doc overlay regression test (seed/edit/diff/validate/apply)
status: open
use-cases: [SUC-001, SUC-002]
depends-on: ['001', '002']
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Multi-doc overlay regression test (seed/edit/diff/validate/apply)

## Description

Prove the full overlay lifecycle end to end over a multi-doc overlay,
and confirm — by test, not by inspection alone — that `generate_diffs`
and `apply` (`src/clasi/design/overlay.py`) require no code changes
under the new slug-keyed manifest, since both already resolve targets
per-file via `_sources.json` rather than by basename or a flat target
directory (confirmed by source reading during architecture review:
`apply`'s docstring states it "never" derives a target from the
overlay filename; `generate_diffs` iterates the overlay directory
per-file).

Seed at least two co-located `DESIGN.md` files from different
subsystems (the issue file's own example pairing:
`src/firm/app/DESIGN.md`-shaped and
`src/host/robot_radio/DESIGN.md`-shaped fixtures, or equivalent fixture
paths available in this repo's test tree), edit both independently,
generate diffs for both, validate the overlay, and apply — asserting
each canonical file receives its own edit and neither is silently
skipped or overwritten by the other's content.

Depends on tickets 001 and 002: exercises both fixes together as an
integration-level regression test, not either in isolation.

## Acceptance Criteria

- [ ] A new test seeds two co-located `DESIGN.md` fixtures (different
      subsystem paths) via `seed_sprint_design_overlay` in one call and
      asserts two distinct overlay files exist with two distinct
      `_sources.json` entries.
- [ ] The test edits both seeded copies with distinguishable content,
      runs `generate_diffs`, and asserts a `.diff.md` sibling exists for
      each edited file with content specific to that file's edit (not
      the other file's).
- [ ] The test runs `clasi design validate` (or the `validate_design`
      MCP tool) against the overlay directory and asserts it passes.
- [ ] The test runs `apply` and asserts each canonical fixture file was
      updated with its own edit — the `firm/app` fixture never receives
      the `host/robot_radio` edit or vice versa.
- [ ] The test asserts `generate_diffs` and `apply` required no source
      changes to pass (i.e., this ticket's diff touches only the test
      file and fixtures, not `overlay.py`'s `generate_diffs`/`apply`
      bodies) — if either turns out to need a change, that is an
      architecture exception to raise, not a silent scope expansion.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "overlay or design"`
- **New tests to write**: the multi-doc lifecycle regression test
  described above, placed alongside existing overlay tests (see
  existing test file location for `seed_and_commit`/`generate_diffs`/
  `apply` coverage).
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
