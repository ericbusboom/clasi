---
id: '003'
title: Rewrite Sprint.detail_promote, archive, and to_dict for single-doc model
status: done
use-cases:
- SUC-004
- SUC-005
- SUC-006
depends-on:
- '001'
- '002'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rewrite Sprint.detail_promote, archive, and to_dict for single-doc model

## Description

Issue B Part 1/4 (Sprint object half). Depends on ticket 001 (landed
first in `sprint.py`, purely additive) and ticket 002 (template
constants already removed). This ticket rewrites three methods in
`src/clasi/sprint.py` together, as one atomic change, per the
architecture-update.md "Shared-File Sequencing" decision:

1. **`Sprint.detail_promote()`** (currently lines ~428-481): remove the
   two blocks that write `usecases_content`/`arch_content` from
   `SPRINT_USECASES_TEMPLATE`/`SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` (now
   deleted by ticket 002 — this rewrite is what actually removes the
   dangling references). Keep: the `roadmap`-phase check, creating
   `tickets/` + `tickets/done/`, updating `sprint.md` frontmatter status
   to `planning-docs`, and `advance_phase()`. Update the "already
   detail-planned" guard (currently checks `self.usecases_md.exists()`)
   to check something meaningful under the new model — e.g. whether
   `tickets_dir` already exists, or whether phase is already past
   `roadmap` — since `usecases_md` no longer gets created by this method
   (but may still exist on old sprints; do not let a stale historical
   `usecases.md` incorrectly block a *different*, newly-created sprint —
   this should not be reachable since sprint dirs are per-sprint, but
   confirm the guard logic explicitly uses this sprint's own state).
   Return dict's `files_written` should reflect the smaller output.

2. **`Sprint.archive()`** (currently lines ~483-517): remove the block
   that copies `architecture_update_md` to `project.architecture_dir`
   (the `shutil.copy2` call and surrounding `if
   self.architecture_update_md.exists()` guard). Keep: updating
   `sprint.md` status to `done`, moving the directory to
   `sprints_dir/done/`, and the `old_path`/`new_path` return.

3. **`Sprint.to_dict()`** (currently lines ~521-537): remove
   `"usecases.md"` and `"architecture-update.md"` keys from the `files`
   dict. Keep `"sprint.md"`.

**Do not** remove the `Sprint.usecases` / `Sprint.architecture` artifact
properties, or the `usecases_md` / `architecture_update_md` path
properties (lines ~101-131) — these must remain as read-only accessors so
historical sprints 001-017 (which still have these files) continue to
render via any status/rendering code that calls them. This ticket only
changes what gets *written*, never what can be *read*.

After this rewrite, grep the repo for any other caller relying on
`to_dict()["files"]` containing the two removed keys (e.g. status
formatting code, tests) and confirm none silently breaks — flag any such
call site found so it can be triaged (fix here if trivial and in scope,
otherwise note for ticket 016's final integration check).

## Acceptance Criteria

- [x] `Sprint.detail_promote()` no longer writes `usecases.md` or
      `architecture-update.md`; it still creates `tickets/` and
      `tickets/done/` and advances phase to `planning-docs`.
- [x] `Sprint.archive()` no longer copies anything to
      `project.architecture_dir`; it still updates status to `done` and
      moves the sprint directory to `sprints/done/`.
- [x] `Sprint.to_dict()["files"]` contains only `"sprint.md"` (drops the
      two removed keys).
- [x] `Sprint.usecases`, `Sprint.architecture`, `Sprint.usecases_md`,
      `Sprint.architecture_update_md` are all still present and unchanged
      — verified by a regression test reading a historical sprint
      fixture (e.g. a fixture modeled on sprint 017's directory layout)
      through these accessors.
- [x] A new sprint run through `create_sprint` → `detail_sprint` (or the
      `Sprint.detail_promote()` method directly in a test) produces
      `sprint.md` + `tickets/` + `tickets/done/` only — no
      `usecases.md`/`architecture-update.md` on disk.
- [x] Closing (archiving) a sprint with an Architecture section inside
      `sprint.md` does not write into `docs/architecture/`.

## Files to create or modify

- `src/clasi/sprint.py` — rewrite `detail_promote()`, `archive()`,
  `to_dict()`.

## Testing

- **Existing tests to run**: `tests/unit/test_sprint.py`,
  `tests/system/test_artifact_tools.py` (any test exercising
  `detail_sprint`, `close_sprint`, or sprint serialization), full
  `uv run pytest`.
- **New tests to write**: `tests/unit/test_sprint.py` —
  `detail_promote()` on a fresh roadmap-phase sprint fixture writes only
  `tickets/`+`tickets/done/`, no usecases/architecture files;
  `to_dict()["files"]` has exactly one key; `archive()` on a sprint with
  an existing `architecture-update.md` does NOT copy it to
  `architecture_dir` (assert the dest file is absent after archiving);
  a backward-compat test that a *historical*-shaped sprint fixture (with
  pre-existing `usecases.md`/`architecture-update.md` on disk, simulating
  sprints 001-017) still has those files readable via
  `Sprint.usecases`/`Sprint.architecture` after this rewrite.
- **Verification command**: `uv run pytest`

## Completion Notes

Implemented together with tickets 002, 004, and 005 as one atomic
commit (they are inseparable at the Python-import level once
templates.py's constants are removed).

The "already detail-planned" guard now checks `self.tickets_dir.exists()`
instead of `self.usecases_md.exists()`, using this sprint's own state as
instructed — a stale historical `usecases.md` (e.g. left over from manual
editing) no longer incorrectly blocks `detail_promote()`, verified by
`test_detail_promote_guard_uses_own_state_not_stale_usecases` in
`tests/unit/test_sprint.py`.

Grepped for other callers relying on `to_dict()["files"]` containing the
two removed keys: none found outside test assertions (all updated in
this batch).
