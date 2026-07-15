---
status: done
sprint: 019
tickets:
- 019-008
---

# Remove leftover docs/architecture/architecture-update-018.md transition artifact

## Description

After sprint 018 closed, a single file remains at
`docs/architecture/architecture-update-018.md` even though sprint 018's
ticket 015 deleted the entire `docs/architecture/` directory (the 17
historical `architecture-update-*.md` files) and ticket 003 removed the
`Sprint.archive()` step that used to copy each sprint's architecture doc
into `docs/architecture/`.

**Why it happened (one-time transition artifact, not a live regression):**
Sprint 018 was itself *planned* under the old three-document model, before
Issue B (single-doc planning) shipped within that same sprint — the
chicken-and-egg the sprint-planner flagged. So sprint 018 had its own
`architecture-update.md`, and a copy landed in `docs/architecture/` and was
swept into the sprint's close commit (`1b65257`), recreating the directory
that ticket 015 had just removed.

**Confirmed not a live regression:** `Sprint.archive()` no longer contains
any copy-to-architecture-dir logic (verified — only an explanatory comment
remains), and `ARTIFACT_PATH_DEFAULTS` no longer defines an `architecture`
path. No sprint planned under the new single-doc model will produce one of
these files.

## Fix

Delete the stray `docs/architecture/architecture-update-018.md` and the
now-empty `docs/architecture/` directory. Cosmetic cleanup, low priority —
safe to fold into any future housekeeping sprint or do out-of-process.

## Related

Sprint 018 (`clasi/sprints/done/018-worktree-parallel-execution-and-right-sized-sprint-planning`),
tickets 003 and 015.
