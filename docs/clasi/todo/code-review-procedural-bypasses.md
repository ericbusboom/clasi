---
status: pending
---

# Code Review: Procedural Code Bypassing Domain Objects

## Summary

`artifact_tools.py` has 24 places where raw procedural operations
bypass the domain objects (Project, Sprint, Ticket, Todo, Artifact,
StateDB) that now exist. The domain objects have the right API but
nothing uses them — the MCP tools still read/write frontmatter
directly, construct paths manually, and call state_db module functions
with string-converted paths.

## Issues Found

### Duplicate Logic (5 issues)

**Issue 1: `_find_sprint_dir` duplicates `Project.get_sprint`**
- Lines 101–117: Iterates sprint directories, reads frontmatter directly.
- Should use: `get_project().get_sprint(sprint_id).path`
- Risk: Three separate implementations of "find sprint by ID" exist
  (this one, Project.get_sprint, and an inline scan at lines 2497–2528).

**Issue 2: `_next_sprint_id` duplicates `Project._next_sprint_id`**
- Lines 146–161: Reads frontmatter from every sprint to compute next ID.
- Should use: `get_project()._next_sprint_id()`

**Issue 3: `_next_ticket_id` duplicates `Sprint._next_ticket_id`**
- Lines 164–178: Takes a raw Path, scans tickets/ directly.
- Should use: `Sprint._next_ticket_id()` on the Sprint object.

**Issue 4: `create_sprint` tool duplicates `Project.create_sprint`**
- Lines 200–257: Manually creates directories, writes files, registers
  in DB with bare `except: pass`.
- Should use: `get_project().create_sprint(title)`

**Issue 13: `_list_active_sprints` duplicates `Project.list_sprints`**
- Lines 260–291: Partial reimplementation with different filtering.
- Should use: `get_project().list_sprints()` with an active-only filter.

### Raw Frontmatter Mutations (7 issues)

**Issue 6: `_renumber_sprint_dir` mutates sprint and ticket frontmatter**
- Lines 306–358: `fm["id"] = new_id`, `write_frontmatter(sprint_file, fm)`,
  then same for every ticket.
- Should use: `sprint.sprint_doc.update_frontmatter(id=new_id)` and
  `ticket._artifact.update_frontmatter(sprint_id=new_id)`.

**Issue 7: `create_ticket` mutates ticket and TODO frontmatter**
- Lines 536–573: Sets `ticket_fm["todo"]`, mutates `todo_fm["status"]`,
  `todo_fm["sprint"]`, `todo_fm["tickets"]`, then renames the TODO file.
- Should use: `Artifact.update_frontmatter(todo=...)` for ticket,
  `project.get_todo(filename).move_to_in_progress(sprint_id, ticket_id)`
  for TODO.
- Risk: `Todo.move_to_in_progress()` already does exactly this. The raw
  code at lines 560–573 duplicates it.

**Issue 8: `update_ticket_status` mutates frontmatter directly**
- Lines 731–758: `fm["status"] = status`, `write_frontmatter(path, fm)`.
- Should use: `ticket.set_status(status)`.

**Issue 9: `move_ticket_to_done` does raw rename and TODO mutation**
- Lines 762–831: Raw `ticket_path.rename(new_path)` bypassing
  `Ticket.move_to_done()`. Then raw TODO frontmatter mutation bypassing
  `Todo.move_to_done()`.

**Issue 10: `reopen_ticket` does raw rename and frontmatter mutation**
- Lines 834–889: `fm["status"] = "todo"`, `write_frontmatter`.
- Should use: `ticket.set_status("todo")` after path adjustment.

**Issue 11: `_close_sprint_legacy` mutates sprint.md and TODOs directly**
- Lines 926–1037: `fm["status"] = "done"`, `write_frontmatter`, raw
  TODO mutations, `shutil.move` on the sprint directory.
- Should use: `sprint.sprint_doc.update_frontmatter(status="done")`,
  `todo.move_to_done()` for each TODO.

**Issue 18: `move_todo_to_done` tool does raw frontmatter mutation**
- Lines 1708–1750: Duplicates `Todo.move_to_done()` logic.
- Should use: `project.get_todo(filename).move_to_done()`.

### Raw State DB Calls (3 issues)

**Issue 19: `_check_sprint_phase_for_ticketing` calls DB module directly**
- Lines 471–493: `_get_sprint_state(str(db), sprint_id)`.
- Should use: `sprint.phase` which delegates to `project.db`.

**Issue 23: `_get_sprint_phase_safe` stringifies `_db_path()` every call**
- Lines 294–303: `_get_sprint_state(str(db), sprint_id)`.
- Should use: `get_project().db.get_sprint_state(sprint_id)`.

**Issue 24: MCP tools for DB operations wrap module functions**
- Lines 1537–1653: `advance_sprint_phase`, `record_gate_result`,
  `acquire_execution_lock`, `release_execution_lock` all call
  `_advance_phase(str(_db_path()), ...)` instead of
  `sprint.advance_phase()`, `sprint.record_gate(...)`, etc.
- Risk: The MCP API and the domain API remain permanently disconnected.

### Direct Frontmatter Reads (4 issues)

**Issue 14: `list_sprints` tool reads frontmatter directly**
- Lines 606–636: `read_frontmatter(sprint_file)` per sprint.
- Should use: `get_project().list_sprints()` + Sprint properties.

**Issue 15: `list_tickets` tool reads frontmatter directly**
- Lines 639–689: `read_frontmatter(f)` per ticket.
- Should use: `sprint.list_tickets()` + Ticket properties.

**Issue 16: `get_sprint_status` reads frontmatter directly**
- Lines 692–724: Two frontmatter reads for one sprint.
- Should use: `sprint.id`, `sprint.title`, `sprint.list_tickets()`.

**Issue 20: Review tools read frontmatter directly**
- Lines 2224–2464: `review_sprint_pre_execution` and
  `review_sprint_pre_close` call `_find_sprint_dir` + raw frontmatter.
- Should use: `sprint.sprint_doc.frontmatter`, `sprint.list_tickets()`.

### Mega-Issue (1 issue, highest risk)

**Issue 12: `_close_sprint_full` — 450 lines, 15+ raw operations**
- Lines 1040–1490: Contains raw frontmatter mutations, raw file renames,
  raw DB calls, raw path construction, raw TODO mutations. Every
  category of bypass exists in this one function.
- Should use: The full domain object API — `Ticket.move_to_done()`,
  `Todo.move_to_done()`, `sprint.advance_phase()`, `sprint.acquire_lock()`,
  `sprint.release_lock()`, `project.db.write_recovery_state()`,
  `project.db.clear_recovery_state()`.
- Risk: Highest in the codebase. Any fix to a domain method won't be
  reflected here because this function has its own inline implementations.

### Other (2 issues)

**Issue 5: `insert_sprint` does all work procedurally**
- Lines 362–468: Combines raw scans, raw frontmatter mutation, raw DB
  calls, and duplicated sprint creation logic.

**Issue 21: `review_sprint_post_close` has third sprint-lookup impl**
- Lines 2497–2528: Inline sprint scan reading frontmatter directly.
- `Project.get_sprint()` already checks both active and done.

**Issue 22: `dispatch_log.py` hardcodes sprint path as string**
- Lines 51–58: `f"docs/clasi/sprints/{sprint_name}"` instead of
  `get_project().sprints_dir / sprint_name`.

## Priority Order

1. **Issue 12** (`_close_sprint_full`) — highest risk, most bypasses
2. **Issues 7, 9, 11, 18** (TODO lifecycle mutations) — duplicated
   logic that will drift from `Todo.move_to_done()` / `move_to_in_progress()`
3. **Issues 8, 10** (ticket status mutations) — `Ticket.set_status()` exists
4. **Issues 24, 19, 23** (DB call wrappers) — Sprint methods exist
5. **Issues 1, 2, 3, 4, 13** (duplicate lookup logic) — Project/Sprint
   methods exist
6. **Issues 14, 15, 16, 20, 21** (direct reads) — Sprint/Ticket objects
   should be constructed once and queried
7. **Issues 5, 6, 17, 22** — lower risk cleanup
