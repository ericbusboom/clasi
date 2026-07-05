---
id: '015'
title: Delete docs/architecture, update dispatch_log context, and verify backward
  compatibility
status: done
use-cases:
- SUC-005
- SUC-006
depends-on:
- '013'
- '014'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Delete docs/architecture, update dispatch_log context, and verify backward compatibility

## Description

Issue B Parts 4/6 (closing work). Depends on ticket 013
(consolidate-architecture already repointed away from
`docs/architecture/`) and ticket 014 (`architecture_dir`/path defaults
already removed from code) so this ticket's deletion has no remaining
code dependency on the directory it's deleting.

1. **`src/clasi/dispatch_log.py`**: update `_auto_context_documents`
   (currently ~lines 43-61) to drop
   `f"{sprint_dir}/architecture-update.md"` and
   `f"{sprint_dir}/usecases.md"` from the returned list — subagent
   dispatch context becomes `sprint.md` (+ the ticket file when
   `ticket_id` is provided), matching the issue's stated intent
   ("subagent context becomes sprint.md + the ticket"). Note: this
   changes context for ALL future dispatches, including to historical
   sprints if any dispatch ever references one — that's fine, since a
   dispatch is always about *current* planning/execution work, never
   about a `done/` sprint.

2. **Delete `docs/architecture/`** from this repository — all 17
   `architecture-update-*.md` files (currently `architecture-update-001.md`
   through `-017.md` based on the sprint numbering; confirm the exact set
   via `ls docs/architecture/` before deleting, since the exact file list
   may include gaps). This is a one-time, explicit deletion as a ticket
   deliverable, not an automated migration script — use `git rm -r
   docs/architecture/` so the deletion is tracked in history.

3. **Backward-compatibility verification** (Issue B Part 6, SUC-005):
   confirm sprints 001-017 in `clasi/sprints/done/` are untouched by
   every ticket in this sprint. Write (or extend an existing) test that:
   (a) calls `list_sprints()`/`get_status()`-equivalent code against the
   real `clasi/sprints/done/001-*` through `017-*` directories (or a
   fixture modeling their shape if operating against the real done/
   directory is impractical in a test) and confirms no exception and
   correct phase/status reporting; (b) confirms
   `Sprint.usecases`/`Sprint.architecture` still return readable
   `Artifact` objects for at least one historical sprint fixture with the
   old three-file layout; (c) confirms `review_sprint_pre_close ` (from
   ticket 005) does not regress against a fixture shaped like a
   historical closed sprint (should already be covered by ticket 005's
   own tests — this ticket's job is to confirm end-to-end, not
   re-implement).

4. Do NOT rewrite, move, or delete any file under `clasi/sprints/done/`
   as part of this ticket — those are the sprints 001-017 that must stay
   exactly as they are.

## Acceptance Criteria

- [x] `dispatch_log.py::_auto_context_documents` returns only
      `sprint.md` (+ ticket file when applicable) — no
      `architecture-update.md`/`usecases.md` entries.
- [x] `docs/architecture/` no longer exists in the repository (removed
      via `git rm -r`, visible in the commit diff as 17 deletions).
- [x] `get_status`/`list_sprints` (or equivalent) against sprints 001-017
      in `clasi/sprints/done/` succeeds without error or behavior change.
- [x] `Sprint.usecases`/`Sprint.architecture` remain readable for at
      least one historical sprint fixture.
- [x] No file under `clasi/sprints/done/` is modified, moved, or deleted
      by this ticket (verify via `git status`/`git diff --stat` scoped to
      that path before finalizing).
- [x] Full `uv run pytest` passes.

## Files to create or modify

- `src/clasi/dispatch_log.py` — `_auto_context_documents`.
- `docs/architecture/` — delete entirely (17 files).
- `tests/` — add or extend a backward-compatibility test (exact file per
  the repo's existing test organization — likely alongside
  `tests/unit/test_sprint.py` or `tests/system/test_artifact_tools.py`).

## Testing

- **Existing tests to run**: `tests/unit/test_sprint.py`, any dispatch-log
  tests (grep `tests/` for `_auto_context_documents` or `dispatch_log`),
  full `uv run pytest`.
- **New tests to write**: `dispatch_log` test asserting the reduced
  context-document list; a backward-compatibility test per item 3 above
  covering `list_sprints`/`get_status`-equivalent behavior and
  `Sprint.usecases`/`Sprint.architecture` accessor reads against a
  historical-shaped sprint fixture.
- **Verification command**: `uv run pytest`
