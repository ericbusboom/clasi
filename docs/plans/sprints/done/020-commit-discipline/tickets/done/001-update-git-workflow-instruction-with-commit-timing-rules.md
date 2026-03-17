---
id: "001"
title: "Update git-workflow instruction with commit timing rules"
status: done
use-cases: [SUC-001]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update git-workflow instruction with commit timing rules

## Description

Add a commit timing section to `instructions/git-workflow.md` that ties
commit points to known-good test states. Currently the instruction covers
conventional commit formatting but says nothing about *when* to commit
relative to test outcomes. This leaves the git history unreliable for
bisection and rollback.

The new section must include:

1. **Run tests before committing** — every commit must represent a state
   where `uv run pytest` passes.
2. **No failing-test commits** — committing with known test failures is
   prohibited, with a documented exception for WIP commits on feature
   branches (never on main/master).
3. **Commit at TDD green phase** — after tests go green, commit
   immediately *before* starting the refactor step.
4. **Separate refactor commits** — refactoring gets its own commit after
   re-running and passing tests, so the green-phase commit and the
   refactor commit are distinct.

Reference the Superpowers TDD skill for details on how commit points
integrate with the red-green-refactor cycle.

## Acceptance Criteria

- [x] `instructions/git-workflow.md` contains a "Commit Timing" section (or equivalent heading)
- [x] The section documents the four rules: run tests first, no failing-test commits, commit at green phase, separate refactor commits
- [x] WIP exception for feature branches is documented with clear guardrails
- [x] Superpowers TDD skill is referenced for commit point details

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — no regressions)
- **New tests to write**: None (content-only change; no Python code modified)
- **Verification command**: `uv run pytest`
