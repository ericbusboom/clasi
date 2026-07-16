---
id: '003'
title: 'Reconcile version-bump policy: fewer bumps without losing live-build signal'
status: open
use-cases: [SUC-003]
depends-on: ['002']
github-issue: ''
issue: version-bump-noise-one-per-ticket-not-per-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Reconcile version-bump policy: fewer bumps without losing live-build signal

## Description

E2E run 003 showed 11 version-bump commits in 36 total (about one per
ticket) — noise with no release value. But `.claude/rules/git-commits.md`
requires a bump per commit specifically because tools are installed
editable and version is how a session tells which code is live. Sprint 019
explicitly deferred reconciling these two positions rather than just
deleting the bumps.

This ticket depends on ticket 002 (stale-install detection) landing first:
once staleness is detected and surfaced automatically, the version bump's
job as a manual "is this live" signal is partially subsumed by an
automatic check, which changes how much bump frequency is actually still
load-bearing. Do not reconcile the policy before reading ticket 002's
actual outcome.

Pick and justify a concrete cadence (e.g., once per sprint, once per
ticket batch, only before `close_sprint` — which already bumps + tags).
The chosen cadence must still let a session answer "is my running build
current" without relying solely on git log inspection, given ticket 002's
detection now exists as a backstop.

## Acceptance Criteria

- [ ] `.claude/rules/git-commits.md` states one concrete, unambiguous bump
      cadence that is not "every commit."
- [ ] The reconciliation explicitly explains why the new cadence still
      satisfies the editable-install "which code is live" need, referencing
      ticket 002's staleness detection as a complementary (not replacement)
      mechanism.
- [ ] A test or documented dry-run on a 3+//-ticket sprint shows at most
      1-2 bump commits for the whole sprint, not one per ticket.
- [ ] `close_sprint`'s own bump+tag behavior is explicitly reconciled with
      the new cadence (no double-bumping, no gap where neither the new
      cadence nor close_sprint covers a scenario).

## Implementation Plan

**Approach**: Read ticket 002's actual delivered mechanism first. Then
rewrite `.claude/rules/git-commits.md`'s bump instruction to a specific,
lower-frequency cadence, and update whatever mechanism currently prompts
per-commit bumps (rule text, and/or a hook if one enforces it) to match.

**Files likely involved**: `.claude/rules/git-commits.md`, any
version-bump-related hook or skill instruction (`instructions/git-workflow`
per the rule's own cross-reference).

**Testing plan**: Dry-run or scripted check across a multi-ticket test
sprint's git log; assert bump-commit count matches the new policy.

**Documentation updates**: `.claude/rules/git-commits.md` is the primary
deliverable; check `instructions/git-workflow` for consistency.
