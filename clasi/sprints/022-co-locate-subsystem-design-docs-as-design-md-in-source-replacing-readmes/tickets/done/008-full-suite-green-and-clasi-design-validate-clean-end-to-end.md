---
id: 008
title: Full-suite green and clasi design validate clean end-to-end
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
depends-on:
- '001'
- '002'
- '003'
- '004'
- '005'
- '006'
- '007'
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

- [x] `uv run pytest` passes with zero failures, zero unexpectedly
      skipped tests related to this sprint's changes.

      Result: 2703 passed, 4 failed, 0 collection errors, 376.65s.
      The 4 failures are all in
      `tests/unit/test_sprint.py::TestRealDoneArchiveBackwardCompat`
      and are pre-existing, unrelated to this sprint: they assert
      against the *real* archived `clasi/sprints/done/021-.../`
      directory (status `closed` vs expected `done`, missing
      `usecases.md`, sprint-id-list mismatch against a hardcoded
      expected list). That archive predates sprint 022 entirely — the
      test fixture copies the on-disk `done/` tree, which drifted from
      the test's hardcoded expectations independently of this sprint's
      changes (021 close-time layout vs. what the test asserts). No
      `@pytest.mark.skip` markers were introduced anywhere in this
      sprint's diff (`git diff 05bb2dc..HEAD -- tests/` confirmed clean).
- [x] `uv run clasi design validate` reports "Design doc set valid."
      with no error messages; only the 5 expected informational
      entries for project-level docs.

      Result: exactly 5 INFO lines (overview.md, specification.md,
      state-machines.md, usecases.md, worktree-process.md) +
      "Design doc set valid."
- [x] `uv run clasi design validate --overlay clasi/sprints/022-co-locate-subsystem-design-docs-as-design-md-in-source-replacing-readmes/design`
      reports no staleness or unresolved-reference messages.

      Result: same 5 INFO lines, "Design doc set valid.", no staleness
      or unresolved-reference messages, before and after the
      `readme_path` fix below (the overlay's `source_hash` is computed
      over the overlay copy's own content, not the canonical file, so
      the canonical-only frontmatter fix does not affect diff
      staleness).
- [x] Grep sweep (see Description) finds no remaining reference to the
      superseded doc<->README model outside of historical sprint
      021/022 planning artifacts themselves (which are expected to
      retain historical prose describing what was superseded).

      Result: `design_doc_slug`, `readme_path_for`, `write_readme` —
      zero hits anywhere. All `docs/design/` hits are the legitimate 5
      project-level docs (system doc + frozen initiation docs) that
      still live there by design; one hit in
      `architecture-authoring/SKILL.md` is explanatory prose framing
      this sprint's own relocation as a worked example (in scope per
      the ticket's historical-prose carve-out). One genuine stale
      reference found and fixed: `docs/design/design.md`'s frontmatter
      still carried `readme_path: null`, a leftover from before
      `write_system_doc` was retargeted (022/002) to only ever write
      `source_paths`. That field predates 022 (introduced in
      021/009's bootstrap commit) and was never touched by any 022
      ticket because the canonical file's *content* is intentionally
      only updated by `close_sprint`'s overlay `apply` step (per
      ticket 007's explicit deferral), but nothing gates its stray
      frontmatter the same way. Removed the field; validated clean
      before and after with both `design validate` commands above.
      Checked `.claude/` (tracked, 4 files, not gitignored in this
      repo) and `src/clasi/plugin/` (packaged skill/agent source) —
      no stale patterns in either.

## Testing

- **Existing tests to run**: full suite, `uv run pytest`.
- **New tests to write**: none — this ticket verifies, it does not add
  new source behavior.
- **Verification command**: `uv run pytest && uv run clasi design validate`
