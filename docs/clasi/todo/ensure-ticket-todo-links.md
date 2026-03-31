---
status: pending
source: https://github.com/ericbusboom/clasi/issues/12
---

# Ensure All Tickets That Implement a TODO Are Linked

## Problem

In sprint 028, only the first ticket was linked to the TODO
(process-redesign-initiation-and-roadmap.md), although all five
tickets in the sprint implemented that TODO. The `create_ticket`
MCP tool only links a TODO when the `todo` parameter is explicitly
passed, and the team-lead only passed it for the first ticket.

## Expected Behavior

Tickets and TODOs have a many-to-many relationship. The link is
mostly informative — if there's any doubt about whether a ticket
relates to a TODO, make the link. When a sprint has one TODO and
multiple tickets, all tickets should be linked to that TODO.

## Proposed Fix

When creating tickets for a sprint that references TODOs in its
sprint.md frontmatter (`todos:` field), automatically link each
new ticket to those TODOs unless the ticket explicitly references
a different TODO. The `create_ticket` tool should:

1. If `todo` parameter is provided, use it (current behavior).
2. If `todo` parameter is NOT provided, check the sprint's
   `todos` frontmatter and link to all of them.

This makes the default behavior "link to the sprint's TODOs"
rather than "link to nothing."
