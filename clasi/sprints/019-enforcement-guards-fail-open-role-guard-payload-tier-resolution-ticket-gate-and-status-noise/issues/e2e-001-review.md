---
id: e2e-001
title: "E2E Test Review — Guessing Game (4 sprints, Docker, Claude print-mode)"
status: pending
type: review
sprint: 019
created: '2026-06-28'
pruned: '2026-07-15'
archived_copy: clasi/review/e2e-001-review.md
tags:
- e2e
- review
- process-improvement
tickets:
- 019-007
- 019-009
---

# E2E Test Review — Guessing Game CLI (pruned)

Post-run review of a full CLASI E2E: 4 sprints driven by Claude Code in
Docker, building a stdlib Python guessing-game CLI from spec. All 4
sprints completed, 37 tests passing, game functional.

**The complete original — all 8 improvement items, the quantitative
summary, and the "What Went Well" section — is preserved verbatim at
[`clasi/review/e2e-001-review.md`](../../../review/e2e-001-review.md).**
This file is pruned by ticket 019-009 to the items that are still live,
so the issue queue reflects outstanding work rather than history.
`clasi/review/` is a plain archival location, not a CLASI-tracked
artifact type — no MCP tooling manages it.

## Live items

### 3. Version bump noise — STILL PENDING

> 11 "chore: bump version" commits in a 40-commit history — one per ticket
> plus one at close. Clutters git history and provides no value for a
> project with no published releases.
>
> **Recommendation:** Bump version once per sprint at close, not per
> ticket. Consider a `--no-bump` flag for tickets that don't introduce
> user-visible changes.

Unchanged and still true — this sprint reproduced the pattern (a version
bump per ticket). Explicitly out of scope for sprint 019 per its
`sprint.md`. This is the sole reason this issue stays `status: pending`.

Note the tension to resolve before acting: `.claude/rules/git-commits.md`
currently *requires* a bump per commit, on the rationale that tools are
installed editable and the version is how a session tells which code is
live. Any fix must reconcile those two positions rather than just
removing the bumps.

### 7. State machine terminology drift — RESOLVED (019-007)

> The state DB records sprints as `phase: done`, but the state machine's
> canonical terminal state is `closed`.

Resolved in this sprint by ticket `019-007`. `Sprint.archive()` now writes
`status: closed` — the machine's only terminal state — instead of `done`,
which `sprint.yaml` never defined. Three regression tests were added,
each verified to fail against the old writer.

Scope note: the 18 sprints archived *before* that fix still carry
`status: done` on disk. Bulk-rewriting them was cut by stakeholder
decision — it rewrites history to satisfy a checker, nothing reads an
archived sprint's declared status, and 019-006 now excludes `done/` from
the status block so the drift warnings no longer surface. The remaining
sub-defect — `detect_inconsistencies` drift-checking terminal, archived
sprints at all — is filed separately and has no visible symptom left.

## Disposition of the other six items

Recorded so no item from the original 8 vanishes without explanation.

| # | Item | Disposition |
|---|------|-------------|
| 1 | Sprint-planner excessively heavy for simple projects | **Still untracked.** Not addressed by any sprint to date. The two-phase roadmap/detail planning model (sprint 018) reduced planning volume but did not add the complexity heuristic this item asks for. Genuinely open — see below. |
| 2 | Serial programmer dispatch wastes time | **Shipped in sprint 018** (worktree parallel execution). Subsequently reverted: the `execute-sprint` skill is now explicitly serial, and worktrees were dropped over accumulation problems. The item's goal is not currently met, but it was addressed and consciously rolled back — not forgotten. |
| 4 | Close reports are inconsistent | **Still untracked.** The `max-turns` exhaustion that caused it is an E2E-harness condition not reproduced in normal operation, and no close-report validation hook exists. Low priority; no symptom outside the E2E run. |
| 5 | No issue tracker integration | **Stale — premise no longer true.** The review found `clasi/issues/` containing only `.gitkeep`. It now holds 4 live and 14 completed issue files and is the queue this very document sits in. |
| 6 | Empty reflections directory | **Stale premise, live recommendation.** The review found `clasi/reflections/` empty; it now holds 7 reflection documents written in normal operation. However, the *recommendation* — a post-close gate requiring a reflection before archiving — was never built (`sprint.yaml` has no reflection predicate). Reflections happen by convention, not enforcement. |
| 8 | Architecture updates are repetitive | **Shipped in sprint 018.** The single-document architecture model replaced per-sprint `architecture-update.md` restatements. Sprint 018's own transition artifact was deleted by ticket `019-008`. |

Items 1 and 4 remain genuinely open but are not tracked as separate
issues. Neither has a current symptom; both are recorded here rather
than filed, and this table is their only record. If either becomes
painful, promote it to its own issue rather than reopening this review.
