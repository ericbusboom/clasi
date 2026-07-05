---
id: '005'
title: Update schema.yaml, review_sprint_pre_close, insert_sprint, and _renumber_sprint_dir
  for single-doc model
status: done
use-cases:
- SUC-004
- SUC-005
depends-on:
- '003'
- '004'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update schema.yaml, review_sprint_pre_close, insert_sprint, and _renumber_sprint_dir for single-doc model

## Description

Issue B Part 2/1 (the `artifact_tools.py` + `schema.yaml` half). Depends
on tickets 003 (Sprint object rewrite) and 004 (state machine + gate
enum) landing first. This is the FIRST of the two `artifact_tools.py`
tickets in this sprint — ticket 008 (Issue A's `_prune_sprint_worktrees`
extension) depends on this ticket so it diffs cleanly against the
post-Issue-B version of the file (see architecture-update.md
"Shared-File Sequencing" — this ordering is deliberate: this ticket does
NOT touch `_prune_sprint_worktrees`, and ticket 008 does not touch any of
the four things this ticket touches).

**1. `src/clasi/schemas/se-process/schema.yaml`**: change the
`generates:` field of the `planning-docs` artifact (currently
`docs/clasi/sprints/<id>/planning-docs/`) and the `architecture-review`
artifact (currently `docs/clasi/sprints/<id>/architecture-update.md`) to
both point at `sprint.md` (its sections). Update the corresponding
`instruction:` references if the instruction files themselves are
renamed or repointed by ticket 012 — coordinate via the `depends-on`
edge from ticket 012 back to this one (ticket 012 depends on this
ticket).

**2. `insert_sprint`** (`src/clasi/tools/artifact_tools.py`, currently
~lines 387-490): remove the loop iteration that writes `usecases.md` from
`SPRINT_USECASES_TEMPLATE` (the `for name, path, template in [...]` block
currently includes `("usecases.md", ...)`) and remove the standalone
block that writes `architecture-update.md` from
`SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`. After this change `insert_sprint`
writes only `sprint.md` (via `SPRINT_TEMPLATE`) plus creates
`tickets/`+`tickets/done/`, matching `Sprint.create_sprint`'s reduced
output. The `files` dict returned should drop the two removed keys to
match `to_dict()`'s new shape from ticket 003.

**3. `_renumber_sprint_dir`** (`src/clasi/tools/artifact_tools.py`,
currently ~lines 335-384): remove `"usecases.md"` and
`"architecture-update.md"` from the reference-rewrite tuple at line
~366 (currently `("usecases.md", "architecture-update.md",
"architecture.md")`). Per architecture-update.md Open Question #3,
**leave `"architecture.md"` in the tuple** — it is an unrelated
pre-existing entry that does not correspond to a file `Sprint` currently
writes and is not part of this sprint's scope to investigate or remove.

**4. `review_sprint_pre_close`** (`src/clasi/tools/artifact_tools.py`,
currently ~lines 2559-2677): remove the `("usecases.md", ...)` and
`("architecture-update.md", ...)` tuples from the
`planning_docs_pre_close` list (currently ~lines 2633-2637), leaving only
`("sprint.md", sprint.sprint_md, SPRINT_TEMPLATE)`. This removes the
per-close "status: draft" friction the issue calls out for those two
files; `sprint.md`'s own draft/placeholder check is unaffected and still
runs.

## Acceptance Criteria

- [x] `schema.yaml`'s `planning-docs` and `architecture-review` artifacts
      both have `generates: .../sprint.md` (or equivalent pointing at
      sprint.md sections, not separate files).
- [x] `insert_sprint` writes only `sprint.md` + `tickets/`+`tickets/done/`
      for the newly-inserted sprint; its returned `files` dict has no
      `usecases.md`/`architecture-update.md` keys.
- [x] `_renumber_sprint_dir`'s reference-rewrite loop no longer attempts
      to rewrite `usecases.md`/`architecture-update.md` bodies; the
      `architecture.md` entry is untouched (still present in the tuple).
- [x] `review_sprint_pre_close`'s `planning_docs_pre_close` list contains
      exactly one tuple (`sprint.md`). Closing a sprint with only a
      finalized `sprint.md` (no usecases/architecture files, or those
      files present but irrelevant) reports `passed: true` for this
      check.
- [x] A sprint inserted via `insert_sprint` immediately after this change
      can be advanced through `planning-docs` → `architecture-review` →
      `stakeholder-review` → `ticketing` using only `sprint.md`.

## Files to create or modify

- `src/clasi/schemas/se-process/schema.yaml`
- `src/clasi/tools/artifact_tools.py` — `insert_sprint`,
  `_renumber_sprint_dir`, `review_sprint_pre_close`.

## Testing

- **Existing tests to run**: `tests/system/test_artifact_tools.py`
  (`insert_sprint`, `_renumber_sprint_dir`/renumbering tests,
  `review_sprint_pre_close` tests), full `uv run pytest`.
- **New tests to write**: `insert_sprint` test asserting only `sprint.md`
  is written; `_renumber_sprint_dir` test with a fixture sprint that has
  no `usecases.md`/`architecture-update.md` (only `sprint.md` +
  `architecture.md`, if that fixture convention is used elsewhere)
  confirming no error and the `architecture.md` body is still
  rewritten if present; `review_sprint_pre_close` test on a
  sprint.md-only sprint returning `passed: true` for the planning-docs
  check; a backward-compat test that `review_sprint_pre_close` on a
  historical-shaped sprint (with the old three files, all finalized)
  still passes.
- **Verification command**: `uv run pytest`

## Completion Notes

Implemented together with tickets 002, 003, and 004 as one atomic
commit.

`review_sprint_pre_execution` (not explicitly named in this ticket's
scope, but sharing the same `SPRINT_USECASES_TEMPLATE`/
`SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` import removed by ticket 002) also
had a `planning_docs` list referencing the two removed constants and
would have raised `NameError` at call time once those constants were
gone. Fixed alongside `review_sprint_pre_close` by trimming its
`planning_docs` list to only `("sprint.md", sprint.sprint_md,
SPRINT_TEMPLATE)`, matching the same single-doc-model shape. Existing
tests exercising draft-status and template-placeholder detection via
`review_sprint_pre_execution` in `tests/system/test_sprint_review.py`
were updated to set the draft/placeholder condition on sprint.md itself,
since it's now the only document checked.

`review_sprint_post_close`'s `post_close_docs` list (lines ~2751-2754)
still references `sprint.usecases_md`/`sprint.architecture_update_md`
but does not import the removed template constants and only checks
`if filepath.exists()` — left untouched as it is harmless (no-op for
new sprints, still-correct draft-status check for historical sprints)
and outside this ticket's named scope.
