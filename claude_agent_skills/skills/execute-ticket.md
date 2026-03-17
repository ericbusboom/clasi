---
name: execute-ticket
description: Executes a single implementation ticket through the full lifecycle — plan, implement, test, document, complete
---

# Execute Ticket Skill

This skill takes a ticket through its full lifecycle from planning to
completion, coordinating multiple agents.

## Agents Used

- **technical-lead** — creates the ticket plan
- **python-expert** (or appropriate dev agent) — implements the code
- **code-reviewer** — reviews the implementation
- **documentation-expert** — updates documentation

## Inputs

- A ticket ID, or picks the next `todo` ticket whose dependencies are all
  `done`

## Process

1. **Select ticket**: Find the next `todo` ticket in the active sprint's
   `tickets/` directory whose `depends-on` entries are all `done`. Read its
   description and acceptance criteria.
2. **Create ticket plan**: Write `NNN-<slug>-plan.md` in the same `tickets/`
   directory, containing:
   - Approach and key design decisions
   - Files to create or modify
   - Testing plan (test type, verification strategy)
   - Documentation updates needed
3. **Set in-progress**: Update the ticket's `status` to `in-progress`.
4. **Implement**: Write the code following the plan. Use the appropriate
   development agent (python-expert for Python work, etc.).
   If TDD is appropriate for this ticket (well-defined interfaces, complex
   logic, bug fixes), consider using the `tdd-cycle` skill for the
   implementation phase. TDD is optional — the agent or stakeholder may
   choose it when it fits, but it is not the default.
5. **Write tests**: Read the ticket's `## Testing` section for guidance
   on which new tests to write and where to place them. Create tests as
   specified, following the testing instructions (unit tests in
   `tests/unit/`, system tests in `tests/system/`, dev tests in
   `tests/dev/`).
6. **Run tests**: Execute the verification command from the ticket's
   `## Testing` section (default: `uv run pytest`). Also run any existing
   tests listed in the Testing section to verify no regressions. All tests
   must pass.
7. **Code review** (agent: **code-reviewer**): Delegate review to the
   code-reviewer agent, which checks:
   - Coding standards (`instructions/coding-standards.md`)
   - Security (no injection, no secrets, safe input handling)
   - Test coverage (every acceptance criterion has a corresponding test)
   - Acceptance criteria (does the code actually satisfy them?)
   The reviewer produces a PASS or FAIL verdict. If FAIL, fix the critical
   findings and request re-review. Do not proceed until the review passes.
8. **Update documentation** (skill: **generate-documentation**): Update any
   docs specified in the plan. Delegate to documentation-expert.
9. **Verify acceptance criteria**: Check every criterion in the ticket.
   All must be met.
10. **Git commit**: Commit all changes from this ticket following the
    conventions in `instructions/git-workflow.md`. The commit message must
    reference the ticket ID and sprint number if working within a sprint
    (e.g., `feat: add auth endpoint (#003, sprint 001)`).
11. **Complete the ticket**:
   - Set `status` to `done` in the ticket's YAML frontmatter.
   - Check off all acceptance criteria (`- [x]`).
   - Move the ticket file to the sprint's `tickets/done/` directory.
   - Move the ticket plan file to the sprint's `tickets/done/` directory.
   - **Commit the moves**: `git add` the moved files and commit with a
     message like `chore: move ticket #NNN to done`.

## Error Recovery

**Test failures:**
When tests fail during step 6, diagnose and fix:

1. Read the error output carefully. Diagnose the root cause.
2. Fix the code (not the test, unless the test is wrong).
3. Re-run the tests. Repeat until all pass.
4. If the failure reveals a flaw in the ticket plan, update the plan.
5. If simple diagnosis does not resolve the failure — especially after
   two consecutive failed fix attempts, or when a previously passing
   test breaks — invoke the `systematic-debugging` skill instead of
   making further speculative changes. The debugging skill provides a
   structured four-phase protocol and caps attempts at three before
   requiring escalation.

## Output

- Implemented code with passing tests
- Updated documentation
- Ticket and plan moved to the sprint's `tickets/done/` directory
