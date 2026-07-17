---
id: '008'
title: Full-suite green and clasi design validate clean end-to-end
status: open
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
depends-on: ['001', '002', '003', '004', '005', '006', '007']
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Full-suite green and clasi design validate clean end-to-end

## Description

Closing ticket. Sweeps for anything the per-module tickets (001-007)
left behind:

- Run the full test suite; fix any remaining failures or dead/skipped
  tests referencing the removed doc<->README pairing (021's backlink
  tests should already be deleted by tickets 002/004, not skipped —
  confirm no `@pytest.mark.skip` was used as a shortcut anywhere in this
  sprint's changes).
- Run `uv run clasi design validate` against this repo's fully migrated
  tree; must report "Design doc set valid." with only the expected
  5 informational entries for the project-level docs (matching the
  planning-time validation run recorded in sprint.md's Process Notes).
- Grep sweep for any remaining generator-source reference (code,
  skills, docs, `CLAUDE.md`, `.claude/` content if not gitignored) to
  the old `docs/design/<slug>.md` shape, `readme_path`, `design_doc_slug`,
  or a subsystem `README.md` design-linking pattern, that tickets
  001-007 didn't already catch. `.claude/` is gitignored per the
  issue's Verification section, so check the packaged plugin source
  (`src/clasi/plugin/`) rather than any installed `.claude/` copy.
- Confirm this sprint's own `design/design.diff.md` is not stale
  (`clasi design validate --overlay <sprint-design-dir>` reports no
  staleness message) as a final check before hand-off to
  architecture-review's re-read / stakeholder-review.

## Acceptance Criteria

- [ ] `uv run pytest` passes with zero failures, zero unexpectedly
      skipped tests related to this sprint's changes.
- [ ] `uv run clasi design validate` reports "Design doc set valid."
      with no error messages; only the 5 expected informational
      entries for project-level docs.
- [ ] `uv run clasi design validate --overlay clasi/sprints/022-co-locate-subsystem-design-docs-as-design-md-in-source-replacing-readmes/design`
      reports no staleness or unresolved-reference messages.
- [ ] Grep sweep (see Description) finds no remaining reference to the
      superseded doc<->README model outside of historical sprint
      021/022 planning artifacts themselves (which are expected to
      retain historical prose describing what was superseded).

## Testing

- **Existing tests to run**: full suite, `uv run pytest`.
- **New tests to write**: none — this ticket verifies, it does not add
  new source behavior.
- **Verification command**: `uv run pytest && uv run clasi design validate`
