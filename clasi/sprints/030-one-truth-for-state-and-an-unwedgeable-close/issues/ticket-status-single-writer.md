---
status: in-progress
type: bug
tags:
- reliability-campaign
- phase-2
- tickets
sprint: '030'
tickets:
- 030-003
---

# Ticket status: one operation moves the file and writes the status

## Description

Moving a ticket to `done/` and writing `status: done` are two separate
operations that no single code path performs together — the YAML action doc
claims one operation does both. Skip either call and the two stores
disagree permanently: frontmatter-based `ticket_counts`/`all_tickets_done`
diverge from the directory-based `is_ticket_in_done_dir`. Ticket globs also
match `*-plan.md` companion files, corrupting counts and `all_tickets_done`.
From the reliability review (01-state-layer.md findings 8, 9; process
review's leaner-flow step 5).

## Acceptance criteria

- `update_ticket_status(path, "done")` sets the frontmatter and performs
  the done-directory move in one call; `move_ticket_to_done` becomes an
  alias or is absorbed, and `reopen` remains the exact converse.
- One shared ticket-listing helper excludes `*-plan.md` and is used by
  `list_tickets`, `all_tickets_done`, and `ticket_count`.
- A test asserts frontmatter and directory agree after every status
  transition, and that a stray plan file affects no counts.
