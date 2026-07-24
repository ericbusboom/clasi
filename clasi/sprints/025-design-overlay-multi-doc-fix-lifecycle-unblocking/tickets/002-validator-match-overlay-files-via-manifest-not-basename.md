---
id: '002'
title: 'Validator: match overlay files via manifest, not basename'
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Validator: match overlay files via manifest, not basename

## Description

`src/clasi/design/validator.py`'s `_canonical_doc_names` (~L221-226)
builds a set of bare canonical basenames (`{"design.md", "DESIGN.md"}`
under the co-located model), and `_check_overlay` (~L229-264) checks
each overlay file's basename against that set. Under the co-located
model this set collapses to two entries regardless of how many distinct
subsystem docs exist, so the check cannot tell which subsystem a given
`DESIGN.md`-named overlay file targets — it can only confirm "some
canonical doc somewhere is named this," which is true of every slugged
overlay file whose basename is preserved, or false in confusing ways
once ticket 001 changes overlay filenames to slugs.

This ticket reworks `_check_overlay` to resolve each overlay file's
recorded canonical target from the `_sources.json` manifest (the same
manifest ticket 001 makes authoritative) and confirm that target is a
real, known canonical doc in the project's doc set — rather than
matching the overlay file's own basename against anything.

Depends on ticket 001: the manifest's key shape (slug, not basename)
must already be in place before the validator can be pointed at it.

## Acceptance Criteria

- [x] `_check_overlay` resolves each overlay file's canonical target via
      `_sources.json`, not via basename-set membership.
- [x] A validation run over an overlay directory containing two or more
      slugged files that both canonically resolve to `DESIGN.md`-named
      docs in different subsystems passes when both targets are real
      and distinct, and reports a clear error naming the specific
      overlay file if either does not.
- [x] An overlay file with no manifest entry (e.g., manually dropped
      into the overlay dir without seeding) is still caught as an
      error, not silently accepted — the fix must not weaken the check
      to "any `.md` file present is fine."
- [x] An overlay file whose manifest entry points to a path outside the
      project's known doc set (system doc + subsystem `DESIGN.md`s) is
      still caught as an error.
- [x] Existing single-doc validation behavior is unchanged in outcome
      for any sprint whose overlay predates this fix and still uses a
      bare canonical basename as both filename and (under ticket 001's
      new manifest) slug.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "validator or design"`
- **New tests to write**: unit tests for `_check_overlay` covering: two
  same-basename overlay files resolving to distinct real canonical
  docs (pass), an overlay file with no manifest entry (fail, specific
  message), an overlay file whose manifest entry points outside the
  doc set (fail, specific message).
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
