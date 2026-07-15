---
id: 008
title: Delete stray docs/architecture/architecture-update-018.md
status: open
use-cases: [SUC-008]
depends-on: ['004']
github-issue: ''
issue: remove-leftover-architecture-update-018-transition-artifact.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Delete stray docs/architecture/architecture-update-018.md

## Description

After sprint 018 closed, `docs/architecture/architecture-update-018.md`
remains on disk even though sprint 018's own ticket 015 deleted the
entire `docs/architecture/` directory and ticket 003 removed the
`Sprint.archive()` step that used to copy each sprint's architecture doc
there. This is a confirmed one-time transition artifact (sprint 018 was
planned under the old three-document model before the single-doc
architecture model shipped within that same sprint), not a live
regression — `Sprint.archive()` no longer contains any copy-to-
architecture-dir logic, and no sprint planned under the current model
will produce one of these files.

Simple deletion. No code changes required — this is the one purely
housekeeping ticket in this sprint's defect list (defect 7's second half,
distinct from defect 6's status-block work).

Root cause reference:
`clasi/issues/remove-leftover-architecture-update-018-transition-artifact.md`.

## Acceptance Criteria

- [ ] `docs/architecture/architecture-update-018.md` no longer exists.
- [ ] `docs/architecture/` directory no longer exists (it becomes empty
      after the file deletion and should be removed, not left as an
      empty directory).
- [ ] No other file references `docs/architecture/architecture-update-018.md`
      (grep the repo for the path before deleting, to confirm nothing
      links to it — if something does, note it in the ticket's
      completion notes rather than silently leaving a broken reference).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — this is a
  deletion with no code path depending on it, but confirm nothing
  breaks).
- **New tests to write**: none required — this is a file deletion, not a
  behavior change. If a test somewhere asserts the file's existence
  (unlikely but check), that test must be removed/updated as part of
  this ticket.
- **Verification command**:
  `test -f docs/architecture/architecture-update-018.md && echo STILL EXISTS || echo GONE`;
  `test -d docs/architecture && echo DIR STILL EXISTS || echo DIR GONE`.
