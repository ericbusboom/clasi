---
status: done
sprint: '024'
tickets:
- 008
---

# TODOs Should Cross-Reference Sprints and Tickets Throughout Their Lifecycle

## Problem

When a TODO is picked up for implementation in a sprint, there is no
visible link back from the TODO to the sprint or ticket that addresses
it. The TODO either disappears (moved to done immediately) or sits in
the pending list with no indication that work is underway. The
stakeholder cannot look at the TODO directory and understand which items
are being actively worked, which sprint they belong to, or which ticket
is handling them.

The existing `move_todo_to_done` tool adds sprint and ticket references
only at the end, when the TODO is moved to done. By that point the
traceability is too late to be useful during the sprint — the
stakeholder wants to see the linkage while work is in progress, not
only after it is finished.

## Proposed Solution

### 1. Update TODO frontmatter when a ticket is created from a TODO

When a ticket is created that addresses a TODO, the TODO's frontmatter
should be updated to reflect the linkage:

```yaml
---
status: in-progress
sprint: "018"
tickets:
  - "018-001"
  - "018-003"
---
```

The status changes from `pending` to `in-progress`, and the sprint and
ticket identifiers are recorded. The TODO stays in the active TODO
directory (not moved to done) so the stakeholder can see it and its
linkage at a glance.

### 2. Keep TODOs visible until the sprint closes

A TODO should not move to `done/` until the sprint that addresses it
has closed successfully. While the sprint is active, the TODO remains
in the main TODO directory with `status: in-progress` and the
sprint/ticket cross-references visible in frontmatter.

When the sprint closes, the TODO moves to `done/` with its final
frontmatter intact (status changes to `done`).

### 3. Update the ticket to reference its source TODO

The reverse link should also exist. When a ticket is based on a TODO,
the ticket's frontmatter or body should reference the source TODO
filename so the link is bidirectional.

### 4. MCP server facilitation

This cross-referencing should be facilitated by the MCP server, not
left to agents to remember. Possible approaches:

- `create_ticket` accepts an optional `todo` parameter (a TODO
  filename or list of filenames). When provided, the tool
  automatically updates the TODO frontmatter with the sprint and
  ticket IDs, and sets the TODO status to `in-progress`.
- `close_sprint` checks for any TODOs linked to the sprint and moves
  them to `done/` as part of the close process.
- `list_todos` shows the sprint/ticket linkage in its output so the
  stakeholder can see which TODOs are in flight.

### 5. Summary of lifecycle

| TODO status   | Location          | Meaning                                    |
|---------------|-------------------|--------------------------------------------|
| `pending`     | `todo/`           | Not yet picked up by any sprint            |
| `in-progress` | `todo/`           | Linked to an active sprint and ticket(s)   |
| `done`        | `todo/done/`      | Sprint completed, TODO fully addressed     |
