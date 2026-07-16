---
status: done
type: bug
source: e2e-test-run-003
clasi_version: 0.20260715.2
tags:
- versioning
- git
- e2e
sprint: '020'
tickets:
- 020-003
---

# Version bump noise: one bump per ticket, not per sprint

## Description

CLASI's git-commits rule generates a version bump commit after every change. In a 4-sprint project with ~3 tickets per sprint, this produces 11–12 version bump commits in 36 total commits — roughly one per ticket plus one at close. The target should be ≤1 bump per sprint (≤4 bumps total).

This clutters git history and provides no value for a project with no published releases. The pattern was documented in e2e-001 review (item 3) and marked as still pending in sprint 019.

## Evidence (e2e run 003)

- **11 version bumps in 36 commits** (31%)
- Previous run (002, old clasi): 12 bumps in 35 commits (34%)
- Every sprint produces 2–3 bump commits: one per ticket implementation + one at close

## Context

The `.claude/rules/git-commits.md` rule currently *requires* a version bump per commit, on the rationale that tools are installed editable and the version is how a session tells which code is live. Sprint 019 explicitly deferred this item, noting:

> "Note the tension to resolve before acting: `.claude/rules/git-commits.md` currently requires a bump per commit... Any fix must reconcile those two positions rather than just removing the bumps."

## Related

- e2e-001 review item 3: version bump noise (still pending)
- Sprint 019: explicitly marked this out of scope
- `clasi/issues/done/e2e-test-plan-002-guessing-game.md` — observation #3