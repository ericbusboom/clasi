---
id: '001'
title: Add completes_todo_for method to Ticket and update move_ticket_to_done archival
  logic
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
depends-on: []
github-issue: ''
todo: clasi-bug-multi-sprint-todos.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add completes_todo_for method to Ticket and update move_ticket_to_done archival logic

## Description

The `move_ticket_to_done` tool in `clasi/tools/artifact_tools.py` unconditionally archives any linked TODO when all referencing tickets are done. This is wrong for multi-sprint umbrella TODOs — a ticket author must be able to signal that moving this ticket to done should NOT trigger archival of the linked TODO.

This ticket introduces `Ticket.completes_todo_for(filename: str) -> bool` — the single place where the new frontmatter field is resolved — and updates `move_ticket_to_done` to call it before archiving each linked TODO.

## Acceptance Criteria

- [x] `Ticket.completes_todo_for(filename)` exists in `clasi/ticket.py`
- [x] Returns `True` when `completes_todo` is absent from frontmatter (backward-compatible default)
- [x] Returns `True` when `completes_todo: true` (scalar)
- [x] Returns `False` when `completes_todo: false` (scalar)
- [x] Returns per-filename value when `completes_todo` is a mapping; absent key defaults to `True`
- [x] `move_ticket_to_done` calls `completes_todo_for` for each linked TODO filename before deciding to archive
- [x] When any linked ticket has `completes_todo: false` for a filename, that TODO is NOT moved to `done/`
- [x] When all linked tickets have `completes_todo: true` (or absent) and all are done, the TODO IS moved to `done/` (existing behavior preserved)
- [x] `result["completed_todos"]` is populated only for actually archived TODOs (not suppressed ones)

## Implementation Plan

### Approach

Add a pure-Python method to `Ticket` that reads its own frontmatter; no file I/O beyond what `Artifact.frontmatter` already does. Update the existing TODO-completion loop in `move_ticket_to_done` to call this method on each ticket that references the TODO under consideration.

### Files to Modify

- `clasi/ticket.py` — add `completes_todo_for(self, filename: str) -> bool` after the `todo_ref` property
- `clasi/tools/artifact_tools.py` — in the `move_ticket_to_done` function, inside the `for todo_filename in todo_list:` loop, after the `all_done` check, add a guard: load each referencing ticket and call `completes_todo_for(todo_filename)`; skip `todo.move_to_done()` if any ticket returns `False`

### Key Implementation Detail

The `completes_todo_for` guard in `move_ticket_to_done` must check every ticket that references the TODO (the same `ref_tickets` list already iterated for `all_done`), not just the ticket currently being moved. A ticket being moved may have `completes_todo: true` but another referencing ticket may have `completes_todo: false` — archival should be suppressed in that case too.

Resolution logic for `completes_todo_for`:
```python
def completes_todo_for(self, filename: str) -> bool:
    val = self.frontmatter.get("completes_todo")
    if val is None or val is True:
        return True
    if val is False:
        return False
    # Map form
    if isinstance(val, dict):
        return bool(val.get(filename, True))
    return True  # fallback for unexpected types
```

### Testing Plan

Add tests to `tests/unit/test_todo_tools.py` or a new `tests/unit/test_ticket.py`:

1. `test_completes_todo_for_absent` — no field → returns `True`
2. `test_completes_todo_for_scalar_true` — `completes_todo: true` → returns `True`
3. `test_completes_todo_for_scalar_false` — `completes_todo: false` → returns `False`
4. `test_completes_todo_for_map_explicit_false` — map with filename → `False`
5. `test_completes_todo_for_map_absent_key` — map without filename → defaults to `True`
6. `test_move_ticket_to_done_archives_single_sprint_todo` — existing behavior: single ticket, no flag, TODO archived
7. `test_move_ticket_to_done_does_not_archive_when_completes_todo_false` — scalar `false` on ticket → TODO not archived
8. `test_move_ticket_to_done_does_not_archive_when_any_ref_ticket_has_false` — two tickets referencing same TODO; one has `completes_todo: false` → TODO not archived even after both are done

### Verification Command

`uv run pytest tests/unit/test_todo_tools.py tests/unit/ -x`
