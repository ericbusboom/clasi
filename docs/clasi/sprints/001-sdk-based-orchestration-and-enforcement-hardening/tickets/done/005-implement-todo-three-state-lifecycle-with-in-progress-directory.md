---
id: '005'
title: Implement TODO three-state lifecycle with in-progress directory
status: in-progress
use-cases:
- SUC-007
depends-on:
- '003'
github-issue: ''
todo: sdk-orchestration-cluster/todo-lifecycle-in-progress-directory.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement TODO three-state lifecycle with in-progress directory

## Description

Extend the TODO system from a two-state model (pending in `todo/`,
done in `todo/done/`) to a three-state model (pending in `todo/`,
in-progress in `todo/in-progress/`, done in `todo/done/`). This
provides visibility into which TODOs are actively being worked and
enables `close_sprint` to verify that all in-progress TODOs for a
sprint have been resolved before closing.

### Directory Support

Add `docs/clasi/todo/in-progress/` directory. Update `init_command.py`
to create this directory during `clasi init`.

### create_ticket Updates

When `create_ticket` is called and the ticket references a TODO:
- Move the TODO file from `todo/` to `todo/in-progress/`.
- Update the TODO's YAML frontmatter: set `status: in-progress`, add
  `sprint` field with the sprint ID, add `tickets` list with the ticket
  ID.
- If the TODO is already in `in-progress/` (referenced by a previous
  ticket in the same or different sprint), only append the new ticket ID
  to the `tickets` list.

### move_ticket_to_done Updates

When `move_ticket_to_done` is called:
- Check if the completed ticket references any TODOs.
- For each referenced TODO, check if all tickets in the TODO's `tickets`
  list have `status: done`.
- If all referencing tickets are done, move the TODO from
  `todo/in-progress/` to `todo/done/` and update frontmatter to
  `status: done`.
- If some tickets are still open, leave the TODO in `in-progress/`.

### close_sprint Verification

Update the `close_sprint` precondition verification to check that all
in-progress TODOs for the sprint are resolved (moved to done
individually by ticket completion). No bulk-move of TODOs occurs at
sprint close -- each TODO must be resolved by its referencing tickets.

### list_todos Updates

Update `list_todos` to correctly report TODOs in the `in-progress/`
directory with their current status and referencing tickets.

## Acceptance Criteria

- [ ] `todo/in-progress/` directory created by `clasi init`
- [ ] `create_ticket` moves referenced TODOs to `in-progress/` and updates frontmatter
- [ ] If TODO is already in-progress, only appends the new ticket ID
- [ ] `move_ticket_to_done` triggers individual TODO completion when all referencing tickets are done
- [ ] TODOs are not bulk-moved at sprint close
- [ ] `close_sprint` verifies all in-progress TODOs for the sprint are resolved
- [ ] `list_todos` reports in-progress TODOs correctly
- [ ] Unit tests for TODO lifecycle transitions

## Testing

- **Existing tests to run**: `tests/test_artifact_tools.py` (create_ticket, move_ticket_to_done, close_sprint)
- **New tests to write**: `tests/test_todo_lifecycle.py` -- tests for: create_ticket moves TODO to in-progress, second ticket appends to existing in-progress TODO, move_ticket_to_done moves TODO to done when all tickets complete, TODO stays in-progress when some tickets remain open, close_sprint blocks on unresolved in-progress TODOs, list_todos reports in-progress status
- **Verification command**: `uv run pytest`
