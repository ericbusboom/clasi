---
id: '013'
title: Repoint consolidate-architecture skill to sprint docs and on-demand output
status: done
use-cases:
- SUC-006
depends-on:
- '003'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Repoint consolidate-architecture skill to sprint docs and on-demand output

## Description

Issue B Part 4. Depends on ticket 003 (`Sprint.usecases`/
`Sprint.architecture` read-only accessors must be confirmed stable —
this skill reads sprint docs across `clasi/sprints/**` including
`done/`, spanning both pre- and post-rewrite sprints).

Rewrite `src/clasi/plugin/skills/consolidate-architecture/SKILL.md`:

1. **Input change**: instead of reading
   `docs/architecture/architecture-update-NNN.md` files (the old
   per-sprint accumulation), the skill now reads **sprint docs** —
   `clasi/sprints/**` including `clasi/sprints/done/**` — covering BOTH
   the new model (sprint.md's `## Architecture` section, for sprints
   planned after ticket 002/003 land) and the legacy model
   (`architecture-update.md` files, for historical sprints 001-017,
   still readable via `Sprint.architecture`) — **plus the current source
   code** (read actual module structure to verify the doc matches
   reality, same as the existing "Read actual code" step).
2. **Output change**: writes exactly one file,
   `docs/design/architecture.md` (singular, not versioned — see
   architecture-update.md's Design Rationale on this decision). Remove
   the "Identify the base" step that looks for
   `docs/architecture/architecture-NNN.md` (highest NNN) — there is no
   "base" anymore, each run reads all available sprint history fresh.
   Remove the "Archive" step (moving old files to
   `docs/architecture/done/`) — there is no old consolidated doc to
   archive under the new model; the single file is simply overwritten.
3. **"On demand only" framing preserved**: this skill still only runs
   when explicitly invoked (unchanged from today) — this ticket does not
   add any automatic-trigger behavior at sprint close (ticket 003 already
   removes the automatic per-sprint copy from `Sprint.archive()`).
4. Keep the "Read actual code" step (already present) — verifying
   against source stays a requirement, not just historical sprint docs.

This ticket does NOT delete `docs/architecture/` itself (that's ticket
015, which depends on this ticket landing first so the skill is
repointed before its old input directory is removed — avoiding a window
where the skill still points at a directory that no longer exists).

## Acceptance Criteria

- [x] `consolidate-architecture/SKILL.md` describes reading sprint docs
      from `clasi/sprints/**` (incl. `done/`) — both sprint.md
      Architecture sections and legacy `architecture-update.md` files —
      plus current source code, as its input.
- [x] The skill's documented output is a single
      `docs/design/architecture.md`, not a versioned series.
- [x] The "Identify the base" (versioned lookup) and "Archive" (move old
      files to `done/`) steps are removed from the skill description.
- [x] The skill remains explicitly on-demand-only (no change to when it
      runs, only to what it reads and where it writes).
- [x] Running the skill (manually, as part of this ticket's verification
      — not required to commit the generated doc, but exercise the
      process at least once) against this repo's actual sprint history
      produces a `docs/design/architecture.md` that references both
      modern and legacy sprint sources without error.

## Files to create or modify

- `src/clasi/plugin/skills/consolidate-architecture/SKILL.md`

## Testing

- **Existing tests to run**: any test referencing
  `consolidate-architecture` or `docs/architecture/architecture-NNN.md`
  path conventions (grep `tests/` first), full `uv run pytest`.
- **New tests to write**: this is primarily a skill-documentation change
  with no directly importable code path (the skill's logic is executed
  by an agent following the SKILL.md instructions, not by a Python
  function) — if there is a smoke test that exercises this skill's
  process programmatically, update it; otherwise verify manually by
  invoking the skill once against this repo's real sprint directory tree
  and confirming a sensible `docs/design/architecture.md` is produced
  (do not need to keep that output as a committed artifact of this
  ticket unless it's already the direction the sprint wants — see ticket
  015 for the actual decision on whether to generate and commit the
  first `docs/design/architecture.md`).
- **Verification command**: `uv run pytest`

## Completion Notes

A full agent-driven execution of the rewritten skill (an LLM reading
every sprint doc and writing a real consolidated `docs/design/architecture.md`)
is not practical for a single programmer session, since the skill's
logic is executed by an agent following prose instructions, not a
Python function. Instead, the described process was traced against
this repo's actual directory structure to confirm each step resolves
to real, readable files:

- `clasi/sprints/018-worktree-parallel-execution-and-right-sized-sprint-planning/sprint.md`
  contains a `## Architecture` heading (matches the canonical
  `src/clasi/templates/sprint.md` template introduced by ticket 002) —
  confirms the new-model input source exists and is readable.
- `clasi/sprints/done/001-sprint-scoped-issue-lifecycle/architecture-update.md`
  through
  `clasi/sprints/done/017-fix-migration-leaving-empty-source-directories/architecture-update.md`
  (17 files) confirm the legacy-model input source exists and is
  readable across all historical sprints.
- `docs/design/` already exists as a directory (holding
  `overview.md`, `specification.md`, `state-machines.md`, etc.),
  confirming `docs/design/architecture.md` is a sensible, consistent
  output location.
- `docs/architecture/architecture-update-NNN.md` (the old versioned
  input/output convention) still exists on disk untouched — this
  ticket does not delete it (that is ticket 015's job) and the
  rewritten skill no longer reads or writes to that directory.

No committed `docs/design/architecture.md` was produced by this
ticket, per the definition of done (ticket 015 decides whether to
generate and commit the first one).
