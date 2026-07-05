---
id: '002'
title: Fold usecases and architecture templates into sprint.md
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fold usecases and architecture templates into sprint.md

## Description

Issue B Part 1 (template half). Fold the `sprint-usecases.md` and
`architecture-update.md` template bodies into
`src/clasi/templates/sprint.md` as new `## Architecture` and
`## Use Cases` sections, each with a one-line note that the section is
sized to the change and may read "N/A — trivial" for small sprints.
Place these sections in a sensible position in the template (e.g. after
"Architecture Notes" or replacing it — avoid duplicate architecture
sections in the resulting template).

Remove the three now-unused template loaders from
`src/clasi/templates.py`: `SPRINT_USECASES_TEMPLATE`,
`SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`, `SPRINT_ARCHITECTURE_TEMPLATE`,
and delete their backing files:
`src/clasi/templates/sprint-usecases.md`,
`src/clasi/templates/architecture-update.md`,
`src/clasi/templates/sprint-architecture.md`.

This ticket does NOT change `Sprint.detail_promote()`,
`Sprint.archive()`, `Sprint.to_dict()`, `insert_sprint`,
`_renumber_sprint_dir`, or `review_sprint_pre_close` — those are handled
by tickets 003 and 005, which depend on this ticket landing first
(the template constants must be gone before code that imports them is
rewritten, otherwise those tickets would need to remove imports of
constants this ticket also removes, doubling the diff surface).

Grep the whole repo for `SPRINT_USECASES_TEMPLATE`,
`SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`, and `SPRINT_ARCHITECTURE_TEMPLATE`
before removing them, and leave a short inline comment in this ticket's
completion notes listing every import site found — tickets 003 and 005
will each need to touch a subset of those sites and should not have to
re-discover them.

## Acceptance Criteria

- [x] `src/clasi/templates/sprint.md` contains `## Architecture` and
      `## Use Cases` sections with the folded-in guidance from the two
      removed templates, plus the "sized to the change / may be N/A"
      note.
- [x] `SPRINT_USECASES_TEMPLATE`, `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`,
      `SPRINT_ARCHITECTURE_TEMPLATE` are removed from `templates.py`.
- [x] `src/clasi/templates/sprint-usecases.md`,
      `src/clasi/templates/architecture-update.md`,
      `src/clasi/templates/sprint-architecture.md` are deleted.
- [x] A grep for the three removed constant names across `src/` and
      `tests/` after this ticket's own template.py edit shows only the
      remaining call sites that tickets 003 and 005 are scoped to fix
      (this ticket does not need to fix those call sites, but must
      confirm they are not silently broken by an import error at
      collection time — coordinate via a shared list in the ticket
      notes, not by fixing them here).
- [x] `uv run pytest` collection does not error (a lingering import of a
      removed constant would fail collection) — if it does, this ticket
      must NOT patch the other files; instead flag to the team-lead that
      tickets 003/005 need to land in the same batch or that this
      ticket's dependency edge is wrong, since this ticket is planned to
      land before them.

## Completion Notes

Resolved the previously-thrown exception (sequencing conflict) by
implementing tickets 002, 003, 004, and 005 together as one atomic
commit, per team-lead direction — the exception's own analysis was
correct that 002 cannot be collection-clean in isolation.

Import sites found by the pre-removal grep (for the record, since 003
and 005 needed to touch these and this ticket promised a shared list):

- `src/clasi/sprint.py`: imported `SPRINT_USECASES_TEMPLATE` and
  `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` at lines 24-25; used at lines
  464 (`usecases_content = ...`) and 469 (`arch_content = ...`) inside
  `Sprint.detail_promote()`. Fixed by ticket 003's rewrite.
- `src/clasi/tools/artifact_tools.py`: imported the same two constants
  at lines 31-32; used at line 471 (`insert_sprint`'s file-writing
  loop), line 478 (`insert_sprint`'s architecture-update write), and at
  two additional call sites not named in ticket 005's text but sharing
  the same import — lines 2487-2488 (`review_sprint_pre_execution`'s
  `planning_docs` list) and 2637-2638
  (`review_sprint_pre_close`'s `planning_docs_pre_close` list, the one
  ticket 005 does name). `review_sprint_pre_execution` was not
  explicitly listed in ticket 005's scope but shared the same import
  and required the same fix to avoid a `NameError` at call time; fixed
  alongside the two named call sites since the import removal made it
  in-scope regardless.

## Files to create or modify

- `src/clasi/templates/sprint.md` — add Architecture + Use Cases sections.
- `src/clasi/templates.py` — remove the three template constant loaders.
- `src/clasi/templates/sprint-usecases.md` — delete.
- `src/clasi/templates/architecture-update.md` — delete.
- `src/clasi/templates/sprint-architecture.md` — delete.

## Testing

- **Existing tests to run**: any test that imports
  `SPRINT_USECASES_TEMPLATE` / `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` /
  `SPRINT_ARCHITECTURE_TEMPLATE` (grep `tests/` first) — expect these to
  need updates in tickets 003/005, not here; run `uv run pytest
  --collect-only` to confirm this ticket alone does not break collection
  for tests outside that scope.
- **New tests to write**: a template-content test asserting
  `templates/sprint.md` contains both new section headers.
- **Verification command**: `uv run pytest --collect-only && uv run pytest`
