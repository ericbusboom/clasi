---
id: "002"
title: "Restructure code-reviewer agent for two-stage review"
status: todo
use-cases: [SUC-002]
depends-on: ["001"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Restructure code-reviewer agent for two-stage review

## Description

Modify the existing `agents/code-reviewer.md` to split the review
process into two explicit, sequential phases:

**Phase 1 — Correctness**: Review the implementation against the ticket's
acceptance criteria and sprint architecture requirements. Each criterion
gets a binary pass/fail verdict. If any criterion fails, Phase 1 fails
and the review stops immediately — Phase 2 is skipped entirely. The
reviewer returns specific failure details so the implementer can fix
the exact issues.

**Phase 2 — Quality**: Only reached if Phase 1 passes. Review against
coding standards, architectural quality, project conventions, and
maintainability. Issues are ranked by severity (critical, major, minor,
suggestion). This separation ensures correctness is never lost in a
pile of style nits.

Read Superpowers `receiving-code-review.md` for details on structuring
review feedback for actionability.

## Acceptance Criteria

- [ ] `agents/code-reviewer.md` defines Phase 1 (correctness) with binary pass/fail per criterion
- [ ] `agents/code-reviewer.md` defines Phase 2 (quality) with severity-ranked issues
- [ ] Phase 1 failure explicitly short-circuits Phase 2 (documented in agent definition)
- [ ] Severity ranking levels are defined (critical, major, minor, suggestion)
- [ ] Agent references the review-checklist template for structured output

## Testing

- **Existing tests to run**: `uv run pytest` — agent listing tests must continue to find code-reviewer
- **New tests to write**: None required (content modification to existing agent definition)
- **Verification command**: `uv run pytest`
