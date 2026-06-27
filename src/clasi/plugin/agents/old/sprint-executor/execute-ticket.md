---
name: execute-ticket
description: Executes a single implementation ticket through the full lifecycle — plan, implement, test, document, complete
---

# Execute Ticket Skill

This skill takes a ticket through its full lifecycle from planning to
completion, coordinating subagent dispatch and two-stage review.

## Agents and Skills Used

- **technical-lead** — creates the ticket plan
- **dispatch-subagent** skill — dispatches isolated implementation subagent
- **subagent-protocol** instruction — context curation rules for dispatch
- **code-reviewer** — two-stage review (correctness then quality)
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
4. **Dispatch implementation subagent** (skill: **dispatch-subagent**):
   Curate context following `instructions/subagent-protocol`, then dispatch
   code-monkey. The controller (this skill)
   does NOT write code directly — all implementation is delegated.

   **Context to include** (per subagent-protocol):
   - Ticket description and acceptance criteria
   - Ticket plan (approach, files to modify, testing plan)
   - Content of source files the subagent will read or modify
   - Relevant architecture decisions from the sprint's `architecture-update.md`
   - Coding standards from `instructions/coding-standards`
   - Testing instructions from `instructions/testing`
   - Git workflow from `instructions/git-workflow`

   **Context to exclude** (per subagent-protocol):
   - Controller's conversation history
   - Other tickets in the sprint
   - Debug logs from prior attempts
   - Full directory listings
   - Sprint-level planning documents (sprint.md, usecases.md)

   After the subagent returns, review the results: read modified files,
   check against acceptance criteria, verify tests pass. If issues are
   found, dispatch a new subagent with feedback (max 3 iterations).

   **Test Driven Development**: If TDD is appropriate for this ticket
   (well-defined interfaces, complex logic, bug fixes), include the
   `tdd-cycle` skill in the subagent's context. TDD is optional — the
   agent or stakeholder may choose it when it fits, but it is not the
   default.
5. **Write tests**: Read the ticket's `## Testing` section for guidance
   on which new tests to write and where to place them. Create tests as
   specified, following the testing instructions (unit tests in
   `tests/unit/`, system tests in `tests/system/`, dev tests in
   `tests/dev/`). Tests may be written by the implementation subagent
   as part of step 4, or dispatched separately.
6. **Run tests**: Execute the verification command from the ticket's
   `## Testing` section (default: `uv run pytest`). Also run any existing
   tests listed in the Testing section to verify no regressions. All tests
   must pass.
7. **Two-stage code review** (agent: **code-reviewer**): Dispatch or
   delegate review to the code-reviewer agent, which performs:
   - **Phase 1 — Correctness**: Binary pass/fail per acceptance criterion.
     If any criterion fails, Phase 1 fails and review stops immediately.
   - **Phase 2 — Quality** (only if Phase 1 passes): Issues ranked by
     severity (critical, major, minor, suggestion) against coding standards.
   The reviewer uses the `templates/review-checklist` template for
   structured output. If the review fails, dispatch a new implementation
   subagent with the review findings as context, then request re-review.
   Do not proceed until the review passes.
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

## Parallel Execution Note

This skill may be invoked inside a git worktree when the project-manager
has opted into parallel execution via the **parallel-execution** skill.
In that case:

- The working directory is an isolated worktree (`../worktree-ticket-NNN`),
  not the main project directory.
- The ticket branch is a per-ticket branch (`ticket-NNN-slug`), not the
  sprint branch directly.
- The core execute-ticket flow does not change — plan, implement, test,
  review, commit, and complete all work the same way.
- Merging the per-ticket branch back to the sprint branch is handled by
  the **parallel-execution** skill after this skill completes, not by
  execute-ticket itself.

Parallel execution is **opt-in only**. Sequential execution on the sprint
branch remains the default. See the **parallel-execution** skill and the
**worktree-protocol** instruction for details.

## Output

- Implemented code with passing tests
- Updated documentation
- Ticket and plan moved to the sprint's `tickets/done/` directory
