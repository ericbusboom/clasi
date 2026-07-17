---
id: '010'
title: 'Fix design-doc slug collision: paths fallback + validator collision detection'
status: done
use-cases:
- SUC-002
- SUC-003
depends-on: []
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix design-doc slug collision: paths fallback + validator collision detection

## Description

Ticket 009 threw an internal exception (see its `exception:` frontmatter
and sprint.md's `## Revision` note): under the single-source-root naming
rule, a subsystem directory literally named `design` (this repo has
`src/clasi/design`) slugifies to `design.md`, which is byte-identical to
`clasi.design.paths.SYSTEM_DOC_NAME` — the fixed, reserved filename of
the top-level system document. Both the subsystem doc and the system doc
resolve to the same path, `docs/design/design.md`, so writing both
silently clobbers one with no error or warning. The validator's
`_check_subsystem_docs` (`src/clasi/design/validator.py`) makes this
worse: its `expected_names` set is a union of `{system_doc_name()}` and
every subsystem's computed slug, so the collision collapses into a
single set entry and the "system doc present" / "subsystem has a doc"
checks both pass even though only one document can physically exist.

This ticket fixes the root cause in `clasi.design.paths` (ticket 002's
module) and closes the corresponding detection gap in
`clasi.design.validator` (ticket 004's module). It must land before
ticket 009 can be reopened and re-run, since 009's bootstrap output
would otherwise reproduce the exact same collision.

**Ordering note**: ticket 009 depends on this ticket (010). Update 009's
`depends-on` frontmatter to include `'010'` if tooling permits; if not,
this dependency is authoritative regardless of what 009's frontmatter
records — do not reopen or re-run 009 until 010 is done.

## Chosen Rule

In `clasi.design.paths.design_doc_slug`: after computing the normal
single-root slug, if it equals `SYSTEM_DOC_NAME` ("design.md"), fall back
to the *existing* multi-root form (root-qualified slug) for that one
subsystem only — e.g. `src/clasi/design` -> `src-clasi-design.md`. This
reuses the multi-root disambiguation rule already implemented (no new
naming concept), so every other subsystem's filename is completely
unaffected, and `design.md` remains reserved for the system doc exactly
as the stakeholder chose. If the disambiguated (root-qualified) slug
*still* equals `SYSTEM_DOC_NAME`, or still collides with another
subsystem's already-computed slug, raise `DesignPathError` — deterministic
and total, but fails loud on the residual pathological case rather than
guessing further or silently colliding.

In `clasi.design.validator._check_subsystem_docs`: replace the
`expected_names` set-union (which silently collapses two subsystems, or a
subsystem and the system doc, mapping to the same filename into one set
entry) with a check that computes each subsystem's slug individually and
detects when two different subsystem paths — or a subsystem and the
system doc — resolve to the same filename. Report this as its own
actionable message (e.g. "Design doc filename collision: subsystem X and
subsystem Y both resolve to <name>"), independent of and in addition to
the existing orphan/unmapped checks.

## Acceptance Criteria

- [x] `design_doc_slug(Path(".../src/clasi/design"), [single_root])`
      returns a filename other than `design.md` (the root-qualified
      fallback, e.g. `src-clasi-design.md` for this repo's actual source
      layout).
- [x] `design_doc_slug` for every other, non-colliding subsystem path is
      byte-identical to its pre-fix output (no behavior change for the
      non-colliding case).
- [x] `design_doc_slug` raises `DesignPathError` when the root-qualified
      fallback itself still equals `SYSTEM_DOC_NAME` or still collides
      with another subsystem's slug (construct a synthetic/parametrized
      case in tests to exercise this — do not rely on finding a real
      pathological repo layout).
- [x] `clasi.design.validator`'s subsystem-doc check detects and reports
      a slug collision between two subsystem paths, and between a
      subsystem path and the system doc, as a distinct, actionable
      message — verified with a test fixture that constructs a colliding
      layout directly (does not require running the fix against this
      repo's live tree, though doing so as a final sanity check is
      encouraged).
- [x] `clasi design validate` (CLI) and `validate_design` (MCP) both
      surface the new collision message identically, consistent with the
      module's existing "both surfaces produce equivalent results"
      contract (see validator.py's module docstring / SUC-003).
- [x] No regression in existing `clasi.design.paths` / `clasi.design.validator`
      tests.

## Implementation Plan

**Approach**: Modify `design_doc_slug` in `src/clasi/design/paths.py` to
detect the single-root collision and reuse the multi-root branch's
computation for that one subsystem, then add a residual-collision check
that raises `DesignPathError`. Modify `_check_subsystem_docs` in
`src/clasi/design/validator.py` to compute slugs individually (not via
set-union) and detect/report duplicates. Keep both changes additive and
narrowly scoped — no change to the multi-root rule's own behavior, no
change to any other function's signature.

**Files to modify**:
- `src/clasi/design/paths.py` (`design_doc_slug`).
- `src/clasi/design/validator.py` (`_check_subsystem_docs`, and
  `_canonical_doc_names` if it needs the same individual-computation
  treatment for the overlay-check path to stay consistent).
- Corresponding test files for both modules (find existing test files
  under the project's test tree for `clasi.design.paths` and
  `clasi.design.validator`; add cases there rather than creating new
  test files unless none exist).

**Testing plan**:
- Unit tests: single-root collision fallback produces the expected
  root-qualified name; non-colliding subsystems unaffected; residual
  collision raises `DesignPathError`.
- Unit tests: validator detects a constructed subsystem/subsystem and
  subsystem/system-doc collision, with a specific actionable message.
- `uv run pytest` full suite, no regressions.
- Optional live sanity check: re-run the slug computation against this
  repo's actual `src/clasi/design` directory and confirm the new
  filename, ahead of ticket 009 being reopened.

**Documentation updates**:
- None beyond this ticket and the sprint.md Revision note already
  written; no user-facing docs describe the naming rule outside
  `paths.py`'s own docstring, which should be updated to describe the
  collision-fallback behavior alongside the existing single-root/
  multi-root rules.
