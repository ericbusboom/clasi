---
id: 009
title: Archive and prune e2e-001-review.md to its live items
status: done
use-cases:
- SUC-009
depends-on:
- '007'
github-issue: ''
issue: e2e-001-review.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Archive and prune e2e-001-review.md to its live items

## Description

`clasi/issues/e2e-001-review.md` (now moved to this sprint's
`issues/e2e-001-review.md` during ticketing) contains 8 numbered
improvement items from a post-run E2E review. Items 2 (parallel
programmer dispatch) and 8 (incremental architecture updates) already
shipped in sprint 018. Item 7 (done/closed terminology) ships in ticket
007 of this sprint. Items 5 (no issue-tracker integration) and 6 (empty
reflections directory) are stale — both `clasi/issues/` and
`clasi/reflections/` are populated directories in active use today, not
empty as the review found them. Only item 3 (version-bump noise) remains
genuinely live and pending — explicitly out of scope for this sprint per
`sprint.md`.

Two steps:

1. Copy the full, unmodified `e2e-001-review.md` to
   `clasi/review/e2e-001-review.md` — a **new** directory. Note in the
   sprint/architecture docs (already done in `architecture-update.md`
   and `sprint.md`) that `clasi/review/` is explicitly NOT a
   CLASI-tracked artifact type (no MCP tooling manages it, it is a plain
   archival copy location for historical review documents).
2. Prune the original (now at
   `clasi/sprints/019-.../issues/e2e-001-review.md`, which
   `move_issue_to_done`-style lifecycle will eventually relocate) down to
   only its two remaining live items: item 3 (version-bump noise, stays
   `pending`) and item 7 (done/closed terminology — mark as resolved by
   this sprint, referencing ticket 007). Add a note stating items 2 and 8
   shipped in sprint 018, and items 5 and 6 are no longer true (with a
   one-line justification for each, as given above).

Depends on ticket 007 — this ticket's pruned text asserts "item 7 is done
in this sprint," which must be true (007 must have actually landed) before
this ticket writes that assertion, not just planned to be true.

Root cause reference: `clasi/issues/e2e-001-review.md` (source review
document); scope boundary set by `sprint.md`'s explicit "item 3 stays
pending" out-of-scope note.

## Acceptance Criteria

- [x] `clasi/review/e2e-001-review.md` exists as a byte-for-byte (or
      near-identical, frontmatter-status-aside) full copy of the original
      8-item review, preserved as historical record.
- [x] The pruned issue file contains only item 3 (version-bump noise,
      `status: pending`, unchanged content) and item 7 (done/closed
      terminology, marked resolved, referencing ticket `019-007`).
- [x] The pruned issue file contains an explicit note that items 2 and 8
      shipped in sprint 018, and items 5 and 6 are no longer true (with
      the one-line justification for each — not just "resolved" with no
      explanation).
- [x] Items 1 and 4 (sprint-planner heaviness, close-report
      inconsistency) are also accounted for in the pruned note — check
      whether they were addressed elsewhere or remain genuinely
      untracked; do not silently drop them without a disposition note
      (the original 8-item list must be fully accounted for: shipped,
      resolved-this-sprint, stale, or still-pending — no item vanishes
      without explanation).
- [x] `clasi/review/` is confirmed to not collide with any existing
      CLASI-tracked artifact directory naming convention (verify against
      `ARTIFACT_PATH_DEFAULTS` in `project.py` — it should not be).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — this is a
  documentation/archival change with no production code path, but
  confirm nothing breaks, e.g. no test globs `clasi/issues/*.md` in a way
  that would be affected by the file's relocation/pruning).
- **New tests to write**: none required — this is a documentation
  archival/pruning task, not a behavior change.
- **Verification command**: `diff <(git show HEAD:clasi/issues/e2e-001-review.md 2>/dev/null || cat clasi/sprints/019-*/issues/e2e-001-review.md) clasi/review/e2e-001-review.md`
  (confirm the archived copy matches the pre-prune original); manual read
  of the pruned file to confirm only items 3 and 7 remain with the
  disposition note for the others.

## Completion Notes

Executed directly by the team-lead: a documentation archival/prune task
whose own Testing section specifies no new tests and no code path.

`clasi/review/e2e-001-review.md` is a byte-for-byte copy of the original
(verified via `diff` — identical, 228 lines, all 8 items intact).
Confirmed `clasi/review/` does not collide with `ARTIFACT_PATH_DEFAULTS`
(issues, sprints, reflections, design, logs, db — no `review` key).

Two ticket claims were checked against the repo rather than taken on
trust, and one needed correcting:

- Item 5 (no issue-tracker integration) — confirmed stale. The review
  found `clasi/issues/` holding only `.gitkeep`; it now has 4 live and
  14 done issue files.
- Item 6 (empty reflections) — **partially stale, not fully.** The
  premise is dead (7 reflection documents exist now, not zero), but the
  ticket's framing of it as simply "no longer true" understates it: the
  item's actual *recommendation* — a post-close gate requiring a
  reflection before archiving — was never built. `sprint.yaml` has no
  reflection predicate. Reflections happen by convention, not
  enforcement. The pruned file records both halves.

Items 1 and 4 were disposed of per the ticket's "no item vanishes"
requirement: both are genuinely still open and untracked, with no current
symptom. Item 2 needed a nuanced disposition — it shipped in sprint 018
and was then consciously reverted (serial execution restored, worktrees
dropped over accumulation), so its goal is unmet but it was not
forgotten.

The pruned file also flags a tension item 3 must resolve before action:
`.claude/rules/git-commits.md` currently *requires* a version bump per
commit, which directly contradicts item 3's "bump once per sprint"
recommendation.
