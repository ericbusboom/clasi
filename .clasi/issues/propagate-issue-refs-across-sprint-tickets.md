---
status: pending
---

# Propagate issue references across all tickets working on the same issue

## Context

When a sprint plans multiple tickets that all work toward the same source issue, only the **first** ticket gets the `issue:` frontmatter ref. The current API is `create_ticket(sprint_id, title, todo=<filename>)`. Only the ticket created with that call gets linked. Subsequent tickets in the same sprint that also implement parts of the same issue have `issue: ""` in their frontmatter.

This was observed in sprint 001 (sprint-scoped-issue-lifecycle): T001 was created with `todo="plan-sprint-scoped-issue-lifecycle-..."`, but T002, T003, T004 were created without it. The issue's `tickets:` frontmatter listed all four (`001-001..004`) — the issue *knew* about the tickets — but the tickets didn't know about the issue. Result: the per-ticket auto-completion in `move_ticket_to_done` never fired for T002/T003/T004 (see also issue [auto-completion-fragility-in-move-ticket-to-done.md](auto-completion-fragility-in-move-ticket-to-done.md)).

## Goal

When multiple tickets are needed to complete a single source issue, all tickets should carry the `issue:` (and `completes_issue:`) frontmatter back-reference. The link should be bidirectional and complete.

## Proposed approach

Two complementary fixes:

1. **Accept a list at create time.** `create_ticket(sprint_id, title, todo=<filename | list[filename]>)` already accepts a list. But the planner has no convenient way to say "this ticket also addresses issue X" *after* the fact, when ticket dependencies are being worked out.

2. **Add an `add_issue_ref(ticket_path, issue_filename)` MCP tool** so the planner (or programmer) can link an issue to a ticket post-creation. The tool would:
   - Append `issue_filename` to the ticket's `issue:` frontmatter (handle string→list conversion).
   - Append the ticket ID to the issue's `tickets:` frontmatter (already done by `Issue.add_ticket_ref` — reuse it).
   - Be idempotent: a second call with the same pair is a no-op.

3. **Sprint-planner guidance update.** The `create-tickets` skill should explicitly tell the planner: *"For every ticket that does work toward an issue, set its `issue:` frontmatter — either via `create_ticket(todo=...)` at creation time, or via `add_issue_ref` afterwards."*

## Files to read

- [clasi/tools/artifact_tools.py:447-505](clasi/tools/artifact_tools.py) — current `create_ticket` and its `todo=` handling
- [clasi/issue.py:113-125](clasi/issue.py) — existing `Issue.add_ticket_ref` (the inverse direction is already there)
- [clasi/ticket.py](clasi/ticket.py) — ticket-side `issue_ref` property
- [clasi/plugin/skills/create-tickets/SKILL.md](clasi/plugin/skills/create-tickets/SKILL.md), [.claude/skills/create-tickets/SKILL.md](.claude/skills/create-tickets/SKILL.md) — planner guidance to update
- [tests/unit/test_issue_tools.py](tests/unit/test_issue_tools.py), [tests/unit/test_issue_lifecycle.py](tests/unit/test_issue_lifecycle.py) — where the tests live

## Out of scope

- Changing the `issue:` frontmatter format itself (still string-or-list).
- Auto-detecting which tickets touch an issue from code analysis.
- The downstream fragility of auto-completion in `move_ticket_to_done` — that's [auto-completion-fragility-in-move-ticket-to-done.md](auto-completion-fragility-in-move-ticket-to-done.md), a separate issue.

## Verification

- Calling `create_ticket(sprint_id, title)` then `add_issue_ref(ticket_path, issue_filename)` produces the same end-state as `create_ticket(sprint_id, title, todo=issue_filename)`.
- Adding a second issue ref to a ticket that already has one converts the field from string → list (or appends to the existing list).
- The issue's `tickets:` frontmatter stays in sync — adding a ref appends; never drops existing entries.
- After all linked tickets are done, `move_ticket_to_done` triggers auto-completion of the issue (assuming the fragility issue is also fixed).
- Idempotent: repeated calls don't duplicate entries.
