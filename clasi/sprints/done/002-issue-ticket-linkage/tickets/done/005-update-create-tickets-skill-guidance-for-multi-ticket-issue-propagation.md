---
id: '005'
title: Update create-tickets skill guidance for multi-ticket issue propagation
status: done
use-cases:
- SUC-002
depends-on:
- '002'
github-issue: ''
issue:
- propagate-issue-refs-across-sprint-tickets.md
completes_issue:
  propagate-issue-refs-across-sprint-tickets.md: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update create-tickets skill guidance for multi-ticket issue propagation

## Description

Update the `create-tickets` skill documentation in both locations to require
that every ticket working toward an issue carries the `issue:` frontmatter
back-reference, and to document the `add_issue_ref` tool (added in ticket 002)
as the mechanism for post-creation linking.

This is a documentation-only change. No code changes.

## Acceptance Criteria

- [x] `.claude/skills/create-tickets/SKILL.md` Step 4 contains an explicit
      "Multi-ticket issue propagation" note explaining the `add_issue_ref`
      requirement.
- [x] `clasi/plugin/skills/create-tickets/SKILL.md` contains the same update
      (both files must stay in sync).
- [x] The note specifies:
      - Use `create_ticket(todo=filename)` for the first ticket.
      - Call `add_issue_ref(ticket_path, issue_filename)` for each subsequent
        ticket working toward the same issue.
      - Before returning from ticket creation, verify every ticket working
        toward an issue has a non-empty `issue:` field.
- [x] Both files are otherwise unchanged (no reformatting, no other edits).

## Implementation Plan

### Approach

Edit the "Issue lifecycle" note in Step 4 of both SKILL.md files to add a
paragraph immediately after the existing note. The insertion point is after:

> "No manual `move_issue_to_done` call is needed in the happy path."

Insert:

> **Multi-ticket issue propagation:** When multiple tickets implement the same
> source issue, every ticket must carry the `issue:` back-reference. Use
> `create_ticket(todo=filename)` for the first ticket. For subsequent tickets,
> call `add_issue_ref(ticket_path, issue_filename)` after creation. Before
> returning from ticket creation, verify that every ticket working toward an
> issue has a non-empty `issue:` field.

### Files to modify

- `.claude/skills/create-tickets/SKILL.md` — add propagation note to Step 4.
- `clasi/plugin/skills/create-tickets/SKILL.md` — same edit.

### Testing plan

- **Existing tests to run**: `uv run pytest` (no code changes, so this is a
  regression-only check).
- **New tests to write**: None — this is a documentation change.
- **Manual verification**: Read both SKILL.md files and confirm the note
  is present and identical in both.
- **Verification command**: `uv run pytest`

### Documentation updates

This ticket is itself the documentation update.
