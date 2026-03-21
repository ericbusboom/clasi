---
id: "008"
title: "TODO-sprint-ticket cross-references"
status: done
use-cases: [SUC-004]
depends-on: []
github-issue: ""
todo: "todo-sprint-ticket-cross-references.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# TODO-sprint-ticket cross-references

## Description

When a TODO is picked up for implementation in a sprint, there is no
visible bidirectional link between the TODO and the sprint/ticket that
addresses it. The TODO either disappears (moved to done immediately) or
sits in the pending list with no indication that work is underway. The
stakeholder cannot look at the TODO directory and see which items are
actively being worked, which sprint they belong to, or which ticket is
handling them.

This ticket implements bidirectional cross-referencing throughout the
TODO lifecycle, plus a new `todo` frontmatter field on tickets pointing
back to their source TODO(s).

### Changes

#### 1. TODO frontmatter updates on ticket creation

When a ticket is created that addresses a TODO, the TODO's frontmatter
should be updated:

```yaml
---
status: in-progress
sprint: "024"
tickets:
  - "024-007"
  - "024-008"
---
```

The status changes from `pending` to `in-progress`, and the sprint and
ticket identifiers are recorded. The TODO stays in the active TODO
directory (not moved to done).

#### 2. Ticket frontmatter `todo` field

Tickets need a frontmatter field pointing back to which TODO(s) they are
sourced from. A TODO might be sourced across multiple tickets, and a
ticket might address multiple TODOs. The field should accept a single
filename string or a list:

```yaml
todo: "fix-todo-delegation.md"
```

or for multiple sources:

```yaml
todo:
  - "team-lead-over-specifies-tickets-to-sprint-planner.md"
  - "fix-todo-delegation.md"
```

#### 3. Keep TODOs visible until sprint closes

A TODO should not move to `done/` until the sprint that addresses it has
closed successfully. While the sprint is active, the TODO remains in the
main TODO directory with `status: in-progress` and the sprint/ticket
cross-references visible in frontmatter.

When the sprint closes, the TODO moves to `done/` with its final
frontmatter intact (status changes to `done`).

#### 4. MCP server facilitation

Update MCP tools to facilitate cross-referencing:

- **`create_ticket`** -- Accept an optional `todo` parameter (a TODO
  filename or list of filenames). When provided, automatically update
  the TODO frontmatter with the sprint and ticket IDs, and set the
  TODO status to `in-progress`.

- **`close_sprint`** -- Check for any TODOs linked to the sprint and
  move them to `done/` as part of the close process.

- **`list_todos`** -- Show the sprint/ticket linkage in its output so
  the stakeholder can see which TODOs are in flight.

#### 5. TODO lifecycle summary

| TODO status   | Location   | Meaning                                  |
|---------------|------------|------------------------------------------|
| `pending`     | `todo/`    | Not yet picked up by any sprint          |
| `in-progress` | `todo/`    | Linked to an active sprint and ticket(s) |
| `done`        | `todo/done/` | Sprint completed, TODO fully addressed |

## Acceptance Criteria

- [x] `create_ticket` MCP tool accepts optional `todo` parameter (filename or list)
- [x] When `todo` is provided, `create_ticket` updates the TODO's frontmatter with sprint ID, ticket ID, and `status: in-progress`
- [x] Ticket frontmatter includes `todo` field pointing to source TODO filename(s)
- [x] `close_sprint` moves linked TODOs to `done/` and sets their status to `done`
- [x] `list_todos` output shows sprint/ticket linkage for in-progress TODOs
- [x] TODOs remain in `todo/` (not `done/`) while their sprint is active
- [x] A TODO can be linked to multiple tickets across the same sprint
- [x] A ticket can reference multiple source TODOs
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `create_ticket` with `todo` parameter updates TODO frontmatter
  - Unit test: `create_ticket` with `todo` list updates multiple TODOs
  - Unit test: `close_sprint` moves linked TODOs to done
  - Unit test: `list_todos` shows sprint/ticket linkage
  - Unit test: TODO stays in `todo/` during active sprint, moves on close
- **Verification command**: `uv run pytest`
