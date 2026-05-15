---
id: '002'
title: Add add_issue_ref MCP tool
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
github-issue: ''
issue:
- propagate-issue-refs-across-sprint-tickets.md
- auto-completion-fragility-in-move-ticket-to-done.md
completes_issue:
  propagate-issue-refs-across-sprint-tickets.md: false
  auto-completion-fragility-in-move-ticket-to-done.md: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add add_issue_ref MCP tool

## Description

Add a new `add_issue_ref(ticket_path, issue_filename)` MCP tool that writes a
bidirectional link between a ticket and an issue post-creation. This fixes the
propagation gap where only the first ticket in a multi-ticket sprint receives
the `issue:` frontmatter back-reference.

The tool is the post-creation complement to `create_ticket(todo=filename)`.
Calling `create_ticket(todo=X)` then `add_issue_ref(ticket_path, X)` produces
the same end-state as `create_ticket(todo=X)` alone, but `add_issue_ref` also
works on tickets that were created without a `todo` parameter.

The inverse direction (`Issue.add_ticket_ref`) already exists in `issue.py`;
this ticket only adds the ticket-side write and the MCP wrapper.

## Acceptance Criteria

- [x] `add_issue_ref(ticket_path: str, issue_filename: str)` is a new
      `@server.tool()` in `clasi/tools/artifact_tools.py`, placed near
      `create_ticket`.
- [x] Resolves `ticket_path` via `resolve_artifact_path`.
- [x] Reads the ticket's `issue:` frontmatter field and handles all three
      cases: absent/empty → sets to `issue_filename`; string → converts to
      `[existing, issue_filename]`; list → appends `issue_filename`.
- [x] Idempotent: if `issue_filename` is already present, makes no change and
      returns without error.
- [x] Calls `project.get_issue(issue_filename)` and then
      `issue.add_ticket_ref(full_ticket_id)` to write the reverse link.
      (`Issue.add_ticket_ref` is already idempotent — no double-entry risk.)
- [x] `full_ticket_id` is constructed as `"<sprint_id>-<ticket.id>"` by
      reading the sprint directory from the ticket's path.
- [x] Returns JSON `{ticket_path, issue_filename, ticket_issue_refs, issue_ticket_refs}`.
- [x] Calling `create_ticket(todo=X)` then `add_issue_ref(path, X)` produces
      the same frontmatter state as `create_ticket(todo=X)` alone.
- [x] Adding a second issue ref (`add_issue_ref(path, Y)` after `issue: X`)
      produces `issue: [X, Y]` on the ticket.

## Implementation Plan

### Approach

New `@server.tool()` placed in `artifact_tools.py` directly after the
`create_ticket` function. No new model methods needed: the ticket side writes
via `ticket._artifact.update_frontmatter(issue=new_value)` (consistent with
the multi-issue path in `create_ticket` at line 491); the issue side calls
`issue.add_ticket_ref(full_ticket_id)`.

To construct `full_ticket_id`, derive the sprint from `ticket_path`:
- Walk up from the ticket file to find `<sprint-dir>/tickets/`.
- Construct `Sprint(sprint_dir, project)`.
- Read `ticket.id` from frontmatter.
- Combine as `f"{sprint.id}-{ticket.id}"`.

### Files to modify

- `clasi/tools/artifact_tools.py` — add `add_issue_ref` tool after
  `create_ticket`.

### Testing plan

- **Existing tests to run**: `uv run pytest tests/unit/test_issue_tools.py tests/unit/test_issue_lifecycle.py`
- **New tests to write** (in `tests/unit/test_issue_tools.py`):
  - Ticket with `issue: ""` → after `add_issue_ref`, `issue: "filename.md"`.
  - Ticket with `issue: "a.md"` → after `add_issue_ref(_, "b.md")`, `issue: ["a.md", "b.md"]`.
  - Ticket with `issue: ["a.md", "b.md"]` → after `add_issue_ref(_, "c.md")`, `issue: ["a.md", "b.md", "c.md"]`.
  - Idempotent: calling twice with same pair → no duplicate, returns same result.
  - Issue's `tickets:` frontmatter gains the ticket ID.
  - End-state equivalence: `create_ticket(todo=X)` vs `create_ticket()` + `add_issue_ref(_, X)`.
- **Verification command**: `uv run pytest`

### Documentation updates

Skill doc update (`create-tickets` SKILL.md) is in ticket 005.
