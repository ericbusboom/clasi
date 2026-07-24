---
id: '005'
title: 'Dogfood: seed and update this sprint''s own affected DESIGN.md docs via overlay'
status: open
use-cases: [SUC-001, SUC-002]
depends-on: ['001', '002', '003', '004']
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Dogfood: seed and update this sprint's own affected DESIGN.md docs via overlay

## Description

This repo has `design_docs: enabled` and `sources: [src/clasi]`. This
sprint's own changes (tickets 001-002) touch canonical docs at
`src/clasi/DESIGN.md` (root), `src/clasi/design/DESIGN.md`, and
`src/clasi/tools/DESIGN.md` — three co-located docs, which is exactly
the multi-doc case this sprint exists to fix. Per sprint.md's
"Design-Overlay Dogfooding Decision," seeding this sprint's own overlay
was deliberately deferred until after the multi-doc fix lands (tickets
001-002), its regression test passes (ticket 003), and the skill prose
describing the seed call is current (ticket 004) — seeding earlier
would hit the very collision being repaired.

This ticket is the last one: call `seed_sprint_design_overlay("025",
["src/clasi/DESIGN.md", "src/clasi/design/DESIGN.md",
"src/clasi/tools/DESIGN.md"])` (exact `doc_names` form per ticket 001's
accepted-forms fix) in one call, confirm three distinct overlay files
and manifest entries result, edit each seeded copy to reflect this
sprint's actual changes (the slug/manifest additions to
`design/DESIGN.md`'s and `tools/DESIGN.md`'s described contracts, and
whatever the root `DESIGN.md` needs updated to reflect), generate
diffs, and validate.

This closes the sprint's own design-doc update obligation using the
sprint's own fix rather than editing the three canonical files directly
(the workaround pattern issue 1 exists to eliminate).

## Acceptance Criteria

- [ ] `seed_sprint_design_overlay` is called once for all three
      affected docs; the sprint's `design/` overlay directory contains
      three distinct files with three distinct `_sources.json` entries
      (no collision, confirming tickets 001-003's fix works on a real
      case, not just test fixtures).
- [ ] Each seeded copy is edited to reflect this sprint's actual
      changes to that doc's described contract.
- [ ] `generate_diffs` produces a `.diff.md` sibling for each edited
      file.
- [ ] `clasi design validate --overlay` (or `validate_design`) passes
      against the sprint's overlay directory.
- [ ] No canonical `DESIGN.md` file under `src/clasi/` is edited
      directly outside the overlay lifecycle as part of this sprint.
- [ ] `apply` is deferred to sprint close (per the standard overlay
      lifecycle — the overlay stays as edited copies until
      `review_sprint_pre_execution`/close applies it), not run early
      by this ticket.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "overlay or design"`
- **New tests to write**: none — this ticket exercises the machinery
  built and tested in tickets 001-003 against real docs; it is a
  dogfooding/documentation ticket, not a code ticket.
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
