---
id: "002"
title: "Update close-sprint and tdd-cycle with commit references"
status: done
use-cases: [SUC-002]
depends-on: ["001"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update close-sprint and tdd-cycle with commit references

## Description

With commit timing rules now defined in git-workflow (ticket 001), two
other process documents need to reference them:

1. **`skills/close-sprint.md`** — Add a test-pass verification gate
   before the merge step. The close-sprint procedure must require that
   `uv run pytest` passes on the sprint branch before merging into main.
   This ensures the merge commit inherits a clean test state.

2. **`skills/tdd-cycle.md`** — Add explicit commit point references
   within the red-green-refactor cycle description. After the green
   phase, the skill should instruct the agent to commit (referencing the
   git-workflow commit timing rules). After the refactor phase, another
   commit point should be specified.

This connects the TDD workflow and sprint closure to the commit
discipline established in ticket 001, making the rules discoverable from
every relevant process document.

## Acceptance Criteria

- [x] `skills/close-sprint.md` includes a test verification step before the merge (e.g., "Run `uv run pytest` and confirm all tests pass before merging")
- [x] `skills/tdd-cycle.md` specifies when to commit during the TDD cycle (after green, after refactor)
- [x] Both documents reference `instructions/git-workflow.md` commit timing rules

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — no regressions)
- **New tests to write**: None (content-only change; no Python code modified)
- **Verification command**: `uv run pytest`
