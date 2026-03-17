---
id: "020"
title: "Commit Discipline"
status: active
branch: sprint/020-commit-discipline
use-cases:
  - SUC-001
  - SUC-002
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 020: Commit Discipline

## Goals

Tie commit points to known-good test states so that every commit in the
git history represents a state where all tests pass. This completes the
TDD integration from sprint 019.

## Problem

CLASI has conventional commit formatting rules but doesn't specify when
to commit relative to test outcomes. The git history may contain commits
where tests are broken, making bisection unreliable and rollbacks risky.

## Solution

Update the git-workflow instruction with commit timing rules:
1. Always run tests before committing
2. No commits with failing tests unless WIP on feature branch
3. Commit at TDD green phase before refactoring
4. Commit refactoring separately after re-running tests

Also update close-sprint to verify all tests pass before merge, and
cross-reference commit points in the tdd-cycle skill.

Reference: Read Superpowers TDD skill for commit point integration.

## Success Criteria

- git-workflow instruction includes commit timing rules
- close-sprint skill verifies tests before merge
- tdd-cycle skill references commit points

## Scope

### In Scope

- Modify instruction: `git-workflow.md`
- Modify skill: `close-sprint.md` (test verification gate)
- Modify skill: `tdd-cycle.md` (commit point references)

### Out of Scope

- Pre-commit hooks (enforcement is instruction-based)
- Modifying state_db.py or artifact_tools.py

## Test Strategy

Content-only sprint. Verification:
- `uv run pytest` (no regressions)
- Manual review of instruction and skill content

## Architecture Notes

Small content-only sprint. No Python code changes.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001** — Update git-workflow instruction with commit timing rules
   - use-cases: [SUC-001], depends-on: []
   - Add commit timing section to git-workflow.md: run tests before committing, no failing-test commits (WIP exception on feature branches), commit at TDD green phase, separate refactor commits
2. **002** — Update close-sprint and tdd-cycle with commit references
   - use-cases: [SUC-002], depends-on: [001]
   - Add test-pass verification gate to close-sprint.md; add commit point references to tdd-cycle.md
