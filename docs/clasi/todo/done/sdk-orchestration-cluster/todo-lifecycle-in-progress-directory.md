---
status: in-progress
sprint: '001'
tickets:
- 001-005
---

# TODO lifecycle: add in-progress directory and granular completion

Currently TODOs move directly from `todo/` to `todo/done/`. This misses an intermediate state when a TODO has been incorporated into a sprint but isn't finished yet.

## Proposed changes

1. **Add `docs/clasi/todo/in-progress/` directory** for TODOs that have been picked up by an active sprint.
2. **When a sprint incorporates a TODO**, move it from `todo/` to `todo/in-progress/`.
3. **TODOs move to `done/` individually**, not all at once when the sprint closes. Each TODO moves to `done/` only when the specific ticket(s) referencing it are closed.
4. **Update the `close-sprint` skill and `move_todo_to_done` tool** to enforce this — closing a sprint should not bulk-move all referenced TODOs to done; only those whose referencing tickets are actually done should move.

## Why

This prevents TODOs from appearing "finished" when their associated work is only partially complete, and gives visibility into which TODOs are actively being worked on.
