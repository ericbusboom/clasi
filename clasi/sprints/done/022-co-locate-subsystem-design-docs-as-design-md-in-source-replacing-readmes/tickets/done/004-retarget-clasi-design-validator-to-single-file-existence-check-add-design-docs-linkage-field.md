---
id: '004'
title: Retarget clasi.design.validator to single-file existence check, add design_docs
  linkage field
status: done
use-cases:
- SUC-002
- SUC-003
depends-on:
- '002'
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retarget clasi.design.validator to single-file existence check, add design_docs linkage field

## Description

Two independent changes bundled because they're both "what does the
system know about a sprint's design-doc changes" and both depend on
ticket 002's retargeted `store.py`:

**1. Validator retarget** (`src/clasi/design/validator.py`):
`_check_subsystem_docs`'s bidirectional link checks (design doc ->
README backlink, README -> design doc backlink, the two "has no
readme_path"/"has no design_doc_path" message branches) are replaced by
a single check: for every subsystem directory, does
`<subsystem_path>/DESIGN.md` exist and is it non-empty (a present but
zero-byte or whitespace-only file is still reported as a failure — an
empty doc is not a valid doc). Keep:
- `_check_system_doc_present` (unchanged — `design.md`'s location is
  unchanged).
- The "unmapped source root" check (subsystem dir with no doc) —
  applies identically, just checking for `DESIGN.md` instead of a doc
  resolving via `design_doc_slug`.
- The filename-collision check is removed entirely — co-located
  `DESIGN.md` files cannot collide (ticket 001 removed the mechanism
  that made collision possible).
- The "orphaned doc" check's *scope* narrows: it no longer applies to
  `docs/design/` subsystem docs (those don't exist anymore after
  ticket 003) — it becomes a check for a stray `DESIGN.md` under a
  directory that isn't a recognized subsystem (e.g. a nested directory
  someone mistakenly added a `DESIGN.md` to, one level too deep). The
  "informational, non-subsystem doc" treatment for the 5 project-level
  `docs/design/*.md` files is unchanged (those files still have no
  frontmatter shape to recognize, and are still exempted the same way).
- Overlay checks (`_check_overlay`) are unchanged in shape — still
  filename-match, frontmatter-reference-resolves, diff-staleness — but
  now operate against whatever canonical doc(s) the overlay targets
  (which may be `docs/design/design.md`, per this sprint's own usage,
  or in principle any `DESIGN.md` once ticket 005 lands).

**2. `design_docs:` sprint/ticket linkage field**: add optional
frontmatter support for a `design_docs:` list (repo-relative
`DESIGN.md` paths) on `sprint.md` and ticket files — the lightweight,
default linkage mechanism sprint.md's SUC-003 and Design Rationale
describe. This is additive schema support (likely in
`clasi.sprint.Sprint`/`clasi.ticket.Ticket` or wherever frontmatter
schema is declared/validated for those artifact types) — a list field,
no special processing beyond being readable/writable like any other
frontmatter list (c.f. `use-cases:`, `depends-on:`).

## Acceptance Criteria

- [x] Validator reports a specific, actionable message per subsystem
      missing a `DESIGN.md`, and per subsystem with an empty
      `DESIGN.md`.
- [x] No code path in `validator.py` references `readme_path`,
      `design_doc_slug`, `readme_path_for`, or the collision-check
      logic after this ticket. (`_check_subsystem_docs`'s bidirectional
      backlink logic and `design_doc_slug`/`readme_path_for`/collision
      checks are fully removed. `_check_overlay`'s frontmatter
      reference-resolution loop still names `readme_path` as one of two
      generic keys it may find in overlay frontmatter — deliberately
      preserved per the ticket's own Description: "Overlay checks
      (`_check_overlay`) are unchanged in shape.")
- [x] The 5 project-level `docs/design/*.md` docs remain
      informational-only (not orphan-errors) after ticket 003's
      migration removes the subsystem docs that used to share that
      directory.
- [x] `sprint.md` frontmatter accepts a `design_docs:` list field
      (read/write round-trip verified); absence of the field is not an
      error (it's optional, matching `use-cases:`'s existing
      "may be empty" pattern).
- [x] A ticket file accepts the same `design_docs:` field for
      per-ticket granularity, if a future sprint wants it (schema
      support only — no MCP tool call is required to add in this
      ticket beyond what's needed for the field to round-trip).

## Testing

- **Existing tests to run**: `tests/design/test_validator.py` (or
  equivalent) — expect significant deletions for the removed
  backlink-check test cases.
- **New tests to write**: single-file existence/non-emptiness checks
  (present, missing, empty-file cases); `design_docs:` frontmatter
  round-trip test on `Sprint`/`Ticket`.
- **Verification command**: `uv run pytest tests/ -k "design or sprint or ticket"`
