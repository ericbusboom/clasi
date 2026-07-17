---
id: '011'
title: 'Fix validator orphan check: frontmatter-shape gate for non-subsystem docs'
status: done
use-cases:
- SUC-003
depends-on:
- '010'
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix validator orphan check: frontmatter-shape gate for non-subsystem docs

## Description

Ticket 009 threw a second internal exception after ticket 010's collision
fix landed and the bootstrap write succeeded cleanly (see ticket 009's
second `exception:` frontmatter entry and sprint.md's `## Revision`
section). `clasi design validate` exited 1 with five "Orphaned design
doc" messages — one per frozen initiation doc (`overview.md`,
`specification.md`, `state-machines.md`, `usecases.md`,
`worktree-process.md`) that sprint.md's Architecture section, Open
Question 2, already approved as coexisting at the top level of
`docs/design/` alongside subsystem docs. Open Question 2's resolution
addressed *filename collision* (confirmed clean by ticket 009); it never
taught `clasi.design.validator` to *recognize* these five files, or any
future non-subsystem prose in `docs/design/`, as legitimate.

This ticket fixes `_check_subsystem_docs`'s orphan-detection logic in
`src/clasi/design/validator.py` (the same module ticket 010 already
touched once this sprint, for the unrelated collision-detection defect).
It must land before ticket 009 is reopened and re-run, since re-running
bootstrap without this fix reproduces the same five-message failure.

**Ordering note**: ticket 009 depends on this ticket (011), in addition
to ticket 010. 009's `depends-on` frontmatter has been updated to
include `'011'`.

## Chosen Rule

The orphan check is revised to key off **frontmatter shape**, not
filename. A `.md` file under `docs/design/` (other than the system doc,
`design.md`) is treated as a subsystem doc — and therefore subject to
orphan-checking against the set of declared subsystems — only if its
frontmatter carries the subsystem-doc shape (`source_paths` and
`readme_path` keys present). This covers the five frozen initiation docs
and any future non-subsystem prose in `docs/design/` without hardcoding
filenames anywhere in the validator.

A plain exempt list of the five known filenames was considered and
rejected: it doesn't generalize to any future non-subsystem doc someone
adds to `docs/design/`, and hardcoding filenames in a structural
validator is exactly the kind of fragile coupling this module's design
otherwise avoids.

The frontmatter-shape test alone (silently skip anything without the
shape) was also considered and rejected as insufficient by itself: a
*stale* subsystem doc whose frontmatter got stripped, corrupted, or
never written correctly would silently evade orphan detection under a
pure skip rule — exactly the drift this check exists to catch.

**Final rule**: a `.md` file without the subsystem-doc frontmatter shape
is not reported as an orphan *error* (so legitimate non-subsystem content
like the initiation docs does not fail `validate`/exit code), but it
*is* surfaced as a separate, distinctly-labeled informational message
(e.g. "Non-subsystem doc (no frontmatter shape recognized):
docs/design/overview.md — not orphan-checked.") that does not count
toward `ValidationResult.ok`. This keeps a stale/corrupted subsystem doc
visible in validator output instead of disappearing from view entirely,
while not blocking legitimate content.

## Acceptance Criteria

- [x] `clasi design validate` (and `validate_design` MCP) exits 0 /
      reports `ok: True` against a `docs/design/` tree containing the
      five frozen initiation docs alongside a correct subsystem doc set
      (construct or reuse a fixture matching this repo's actual
      post-bootstrap shape).
- [x] A `.md` file in `docs/design/` with no frontmatter, or frontmatter
      lacking both `source_paths` and `readme_path`, does not produce an
      "Orphaned design doc" error.
- [x] The same frontmatter-less file produces a distinct informational
      message (verify it is present in `ValidationResult.messages` but
      does not flip `ValidationResult.ok` to `False` on its own — use a
      structured way to distinguish informational from error messages,
      e.g. a message-kind field or a clearly distinguishable prefix;
      pick an approach consistent with `ValidationResult`'s existing
      shape and document the choice in the module docstring).
- [x] A genuine orphan — a `.md` file *with* the subsystem-doc
      frontmatter shape (`source_paths`/`readme_path`) but no matching
      declared subsystem directory — is still reported as an orphan
      error exactly as before (no regression on the check's actual
      purpose).
- [x] A stale subsystem doc with frontmatter stripped/corrupted is still
      visible in validator output via the new informational message
      (does not vanish silently) — add a test constructing this case
      directly.
- [x] `clasi design validate` (CLI) and `validate_design` (MCP) surface
      both the informational message and the exit-code/`ok` distinction
      identically.
- [x] No regression in existing `clasi.design.validator` tests, including
      ticket 010's collision-detection tests.

## Implementation Plan

**Approach**: Modify `_check_subsystem_docs` in
`src/clasi/design/validator.py`. Where the current orphan loop iterates
`design_dir`'s `.md` files and checks membership in `expected_names`,
first check the file's frontmatter for the subsystem-doc shape
(`source_paths`/`readme_path` both present). If absent, skip the
orphan-error path and instead append an informational entry (using
whatever mechanism is chosen to distinguish it from
`ValidationResult.messages`'s error entries — extend the dataclass if
needed, e.g. an `info: list[str]` field alongside `messages`, keeping
`ok` defined purely off `messages`). If present, proceed with the
existing `expected_names` membership check unchanged.

**Files to modify**:
- `src/clasi/design/validator.py` (`_check_subsystem_docs`,
  `ValidationResult` if a new field is needed, module docstring's
  "Message format contract" section to describe the informational
  channel).
- `src/clasi/tools/artifact_tools.py` or wherever `validate_design`
  (MCP) and the `clasi design validate` CLI command format output, if
  either needs updating to surface the new informational channel
  distinctly from errors.
- Corresponding test file(s) for `clasi.design.validator` — add cases
  rather than creating a new test file unless none exists.

**Testing plan**:
- Unit tests: frontmatter-less doc produces info not error; doc with
  subsystem-doc frontmatter shape but no matching subsystem still
  produces an orphan error; stale/corrupted subsystem doc (frontmatter
  stripped) produces the informational message rather than silently
  passing.
- Fixture matching this repo's real post-bootstrap `docs/design/` shape
  (5 initiation docs + subsystem docs + system doc) validates clean.
- `uv run pytest` full suite, no regressions.
- Optional live sanity check: run `clasi design validate` against this
  repo's actual `docs/design/` tree (once ticket 009 re-runs bootstrap)
  and confirm exit 0, ahead of closing out ticket 009.

**Documentation updates**:
- Update `validator.py`'s module docstring ("Message format contract"
  section) to describe the new informational-vs-error distinction
  alongside the existing collision-detection note from ticket 010.
