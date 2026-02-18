---
status: pending
---

# Add Sprint Review MCP Tools (Pre-Execution, Pre-Close, and Post-Close)

Add three MCP tools that validate sprint state at critical lifecycle checkpoints, preventing sprints from advancing with incomplete or incorrectly-statused artifacts.

## Problem

Sprints are currently being closed with planning files (sprint.md, technical-plan.md, usecases.md) still in draft status. There is no automated validation that sprint artifacts are complete and correctly statused before execution begins or before the sprint is closed.

## Proposed Tools

### 1. `review_sprint_pre_execution`

Called **after tickets are created but before they are implemented** (i.e., before advancing to the execution phase). Validates:

- Currently on the correct sprint branch
- Sprint directory exists
- `tickets/` directory exists
- `sprint.md` exists with correct frontmatter status (not draft)
- `technical-plan.md` exists with correct frontmatter status (not draft)
- `usecases.md` exists with correct frontmatter status (not draft)
- All planning files contain real content (not default template content)
- All tickets exist and are in `todo` status

Returns a pass/fail result with a list of issues found.

### 2. `review_sprint_pre_close`

Called **after tickets are implemented but before the sprint is closed** (i.e., before the agent hands control back to the user or closes the sprint in auto-approve mode). Validates:

- Currently on the correct sprint branch
- All tickets are in `done` status
- All ticket files are in the `tickets/done/` directory
- `sprint.md` has correct completed/active status (not draft)
- `technical-plan.md` has correct status (not draft)
- `usecases.md` has correct status (not draft)
- Planning files contain real content, not default template placeholders
- All artifacts have appropriate frontmatter state for a completed sprint

Returns a pass/fail result with a list of issues found.

### 3. `review_sprint_post_close`

Called **after the sprint is closed** to verify everything is fully wrapped up. Validates:

- All tickets are in `done` status
- All ticket files are in the `tickets/done/` directory
- All planning documents (`sprint.md`, `technical-plan.md`, `usecases.md`) have correct final status (not draft)
- The sprint directory has been moved to `sprints/done/`
- The sprint branch has been committed (no uncommitted changes)
- Currently back on the master branch

Returns a pass/fail result with a list of issues found.

## Error Reporting

Each tool must return structured JSON with:

- `passed`: boolean
- `issues`: array of issue objects, each with:
  - `severity`: `"error"` (must fix) or `"warning"` (should fix)
  - `check`: short machine-readable check name (e.g., `"sprint_md_status"`, `"ticket_not_done"`)
  - `message`: human-readable description of the problem
  - `fix`: explicit instruction on how to correct the issue (e.g., `"Update sprint.md frontmatter status from 'draft' to 'active' using write_artifact_frontmatter"`)
  - `path`: file path involved, if applicable

The `fix` field is critical — agents must be able to read the issue list and correct every problem without guessing. If a review does not pass, the agent must iterate: fix all reported issues, then re-run the review tool until it passes. The agent must not proceed past a review checkpoint until the review returns `passed: true`.

## Integration Points

- `review_sprint_pre_execution` should be called by the `advance_sprint_phase` tool (or by the agent) when transitioning from planning-docs to execution
- `review_sprint_pre_close` should be called by the `close_sprint` tool (or by the agent) just before closing the sprint
- `review_sprint_post_close` should be called after `close_sprint` completes, before the agent hands control back to the user
- All three tools should return structured JSON as described in Error Reporting above
- **Agents must not skip reviews.** If a review fails, the agent must fix all issues and re-run the review until it passes before proceeding

## Testing Requirements

This feature requires comprehensive test coverage because the tools must correctly detect many distinct failure states.

### Unit Tests (construct sprint fixtures in various broken states)

For each of the three review tools, test at minimum:

- **Happy path**: a fully correct sprint passes review
- **Missing files**: sprint.md, technical-plan.md, usecases.md, or tickets/ missing
- **Wrong frontmatter status**: each file in draft when it shouldn't be, wrong status values
- **Template placeholder content**: files that still have default template text (not real content)
- **Ticket state issues**: tickets not in done status, ticket files not in done/ directory, mix of done and not-done tickets
- **Branch issues**: wrong branch checked out, uncommitted changes on branch
- **Post-close specifics**: sprint directory not moved to done/, not on master branch

Each test should verify that the returned `issues` array contains the correct check names, actionable `fix` instructions, and accurate file paths.

### Regression Tests (run reviews against historical sprints)

Run the review tools against completed sprints in `docs/plans/sprints/done/` to:

- Verify that the tools correctly identify known issues in earlier sprints (e.g., draft status on planning files)
- Establish a baseline of what "good" and "bad" look like with real data
- Ensure the tools don't produce false positives on sprints that are actually correct

These regression tests serve as documentation of what earlier sprints got wrong and confirm the tools would have caught those issues.
