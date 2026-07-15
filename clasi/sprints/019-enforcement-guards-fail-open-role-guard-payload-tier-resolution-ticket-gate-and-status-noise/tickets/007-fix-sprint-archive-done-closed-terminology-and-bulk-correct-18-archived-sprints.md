---
id: '007'
title: Fix Sprint.archive() done/closed terminology and bulk-correct 18 archived sprints
status: open
use-cases:
- SUC-007
depends-on:
- '004'
github-issue: ''
issue:
- e2e-001-review.md
- enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue:
  e2e-001-review.md: false
  enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix Sprint.archive() done/closed terminology and bulk-correct 18 archived sprints

## Description

The sprint state machine's canonical terminal state has always been named
`closed` (`src/clasi/schemas/state-machines/sprint.yaml`, unchanged
across all prior sprints — see the `closed:` state block and its
invariants `is_close_report_present`/`is_branch_merged`/
`is_review_satisfied`). `Sprint.archive()` (`src/clasi/sprint.py:498`)
writes `status: "done"` to `sprint.md` frontmatter on archive — `done` is
not a state the machine defines. Every one of the 18 sprints currently in
`clasi/sprints/done/` was archived with this writer and carries
`status: done`, which `detect_inconsistencies`
(`status/inconsistency.py`) permanently flags as `state_drift` (declared
`done` vs. computed `closed`) — this is the direct cause of the 18 bogus
drift warnings referenced by `e2e-001-review.md` item 7, and (before
ticket 006's done/-exclusion fix) was part of what made the 34KB status
block so noisy.

Two parts:

**Part A — fix the writer.** Change `Sprint.archive()` to write
`status: "closed"` instead of `status: "done"`. This only affects
sprints archived *after* this ticket ships — it does not retroactively
fix the 18 existing files.

**Part B — bulk-correct history.** Write a one-time script (can be a
throwaway script run once and not committed, or a small permanent
migration utility — implementer's judgment, but document which in the
implementation notes) that rewrites `status: done` to `status: closed` in
the frontmatter of all 18 `clasi/sprints/done/*/sprint.md` files. This is
mechanical and low-risk: `sprint.yaml`'s `closed` state has no outbound
transitions, so nothing downstream re-evaluates differently as a result
— this is a frontmatter-accuracy fix only, not a behavior change for any
of the 18 archived sprints.

Depends on ticket 004 only for sequencing (this ticket's own execution,
like every ticket after 004, runs under the live ticket-state gate — no
code dependency on 004's actual logic). Independent of ticket 006's
status-block code changes; either could execute first, but this ticket
comes second by convention (both are status/terminology-related, and 006
already established the `done/`-exclusion context this ticket's fix
complements).

Root cause reference:
`clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 7 (the `done`/`closed` mismatch, as it drives status-block noise)
and `clasi/issues/e2e-001-review.md` item 7 (the same drift, reported
independently from the E2E test review). This ticket is the completing
ticket for the enforcement issue (`completes_issue: true` for that file)
— it does not complete `e2e-001-review.md`, which still has item 3
(version-bump noise) pending; see ticket 009 for the archive/prune of
that issue.

## Acceptance Criteria

- [ ] `Sprint.archive()` writes `status: "closed"` (not `"done"`) to
      `sprint.md` frontmatter.
- [ ] Test: archiving a sprint via `Sprint.archive()` produces
      `status: closed` in the resulting frontmatter, and
      `detect_inconsistencies` reports zero `state_drift` for that
      sprint immediately after archiving (declared now matches computed).
- [ ] All 18 existing `clasi/sprints/done/*/sprint.md` files have
      `status: done` rewritten to `status: closed` in place.
- [ ] `grep -c "^status: done" clasi/sprints/done/*/sprint.md` returns 0
      for every one of the 18 files (verify by running the actual
      command against this repo, not just by inspection).
- [ ] No other frontmatter field in any of the 18 files is altered by the
      bulk-correction (verify via diff — the change should be a
      single-line `status:` value swap per file, nothing else).
- [ ] Existing sprint-lifecycle tests (`Sprint.archive()`,
      `detect_inconsistencies`) still pass after the writer change.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_sprint*.py tests/unit/test_status/ -v`
- **New tests to write**: `Sprint.archive()` writes `closed` test;
  post-archive zero-drift test.
- **Verification command**:
  `grep -c "^status: done" clasi/sprints/done/*/sprint.md` (expect 0 for
  every file); `uv run pytest tests/unit/test_sprint*.py tests/unit/test_status/ -v`
