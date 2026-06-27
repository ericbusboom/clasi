---
status: done
sprint: 008
tickets:
- 008-001
---

# `read_frontmatter` silently returns empty fields when the opening `---` fence is corrupted

## Context

Discovered while debugging why `close_sprint` reported "Sprint '007' not found in active or done" even though the sprint directory and `sprint.md` were present.

The actual cause: line 1 of `sprint.md` was `pwd---` instead of `---`. The YAML frontmatter parser did not recognize `pwd---` as a valid opening fence, so it returned a frontmatter dict with empty strings for every field. `project.get_sprint(sprint_id)` at [clasi/project.py:87](clasi/project.py) iterates sprint directories and matches `fm.get("id") == sprint_id`. With `id == ""`, the match never succeeds and the sprint appears not to exist.

Observed in `list_sprints` output before the fix:

```json
{
  "id": "",
  "title": "",
  "status": "unknown",
  "path": ".../007-close-sprint-mcp-workaround-finalize-sprint-alias-and-cli",
  "branch": ""
}
```

The sprint directory is listed (so `iterdir` and the loop see it), but the frontmatter parse produced empty values for every key.

## The bug

`read_frontmatter` (in `clasi/frontmatter.py`) treats "no recognizable frontmatter" the same as "valid frontmatter with empty values." A garbage first line (`pwd---`, `xyz---`, `---x`, etc.) silently turns into an empty dict — no warning, no exception, no log.

Callers that key off frontmatter fields (`get_sprint`, `list_sprints`, `Ticket.status`, etc.) then operate on empty values and produce downstream errors that point in the wrong direction.

## Proposed behavior

When a `sprint.md` / `ticket.md` / issue file has content but no recognizable frontmatter, `read_frontmatter` should at minimum log a warning identifying the file. Ideally it should raise a typed exception (`MalformedFrontmatterError`) that callers can catch and surface clearly.

A diagnostic check at startup that scans known artifact files and reports any with malformed frontmatter would catch this class of corruption before it shows up as a misleading "not found" error.

## Reproduction

1. Create a sprint directory with a `sprint.md` whose first line is `pwd---` instead of `---`.
2. Call `mcp__clasi__list_sprints()` — the sprint appears with all empty fields.
3. Call `mcp__clasi__get_sprint_status(sprint_id="007")` — fails with "Sprint '007' not found".
4. Call `mcp__clasi__close_sprint(sprint_id="007", ...)` — fails the precondition with the same "not found" message.

## Acceptance

- `read_frontmatter` emits a `WARNING` (or raises) when a file has content but no recognizable opening fence.
- The misleading "not found" cascade no longer fires for this case; instead the actual cause (malformed file) is reported.
