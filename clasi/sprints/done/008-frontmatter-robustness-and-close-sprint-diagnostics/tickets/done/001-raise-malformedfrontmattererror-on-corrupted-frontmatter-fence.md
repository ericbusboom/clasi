---
id: '001'
title: Raise MalformedFrontmatterError on corrupted frontmatter fence
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: frontmatter-silent-on-malformed-fence.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Raise MalformedFrontmatterError on corrupted frontmatter fence

## Description

`read_frontmatter` currently returns an empty dict when a file has content but
its first line is not a valid `---` opening fence (e.g. `pwd---`, `---x`,
`xyz---`). This silent behavior causes a cascade of misleading "not found"
errors in callers that key off frontmatter fields.

This ticket adds a typed `MalformedFrontmatterError` exception (subclass of
`ValueError`) to `clasi/frontmatter.py` and raises it from `_parse` (and
transitively from `read_document` / `read_frontmatter`) when a file has content
but its first line starts with `-` yet is not a valid `---` fence.

It also updates `project.py` to define typed sprint exception classes and update
`get_sprint` and `list_sprints` to use them. Ticket 002 depends on these typed
exceptions being in place.

## Acceptance Criteria

- [x] `MalformedFrontmatterError` is defined in `clasi/frontmatter.py` as a
      subclass of `ValueError`.
- [x] `read_frontmatter` raises `MalformedFrontmatterError` when the file has
      non-empty content whose first line starts with `-` but is not exactly
      `---`.
- [x] The exception message includes the file path and the actual first-line
      text found.
- [x] `read_frontmatter` continues to return `{}` for files that genuinely have
      no frontmatter (first character is not `-`) — existing guard clause
      behavior preserved.
- [x] `SprintNotFoundError`, `SprintFrontmatterError`, and
      `SprintIdMismatchError` are defined in `clasi/project.py`, each as a
      subclass of `ValueError`.
- [x] `project.get_sprint` raises `SprintFrontmatterError` (naming the
      `sprint.md` path and the parse failure) when frontmatter is malformed.
- [x] `project.get_sprint` raises `SprintIdMismatchError` when frontmatter
      parses but the `id:` field is absent or does not match the requested ID.
- [x] `project.get_sprint` raises `SprintNotFoundError` when no matching
      directory is found (preserving the existing message).
- [x] `project.list_sprints` catches `MalformedFrontmatterError` per file,
      logs a `WARNING` naming the file, and continues iteration without halting.
- [x] All existing tests pass without modification.
- [x] New unit tests cover: malformed fence raises, genuine no-frontmatter
      returns `{}`, `get_sprint` typed exceptions for each sub-case, and
      `list_sprints` continues past a corrupt file.

## Implementation Plan

### Approach

Bottom-up: fix the parser first, then thread typed exceptions up through
`project.py`. Ticket 002 builds on these foundations.

### Files to modify

**`clasi/frontmatter.py`**

1. Add `MalformedFrontmatterError(ValueError)` class near the top of the file,
   before `read_document`.
2. Update `_parse` to accept an optional `source_path: str | Path | None = None`
   parameter for use in error messages.
3. Replace the existing guard clause:
   - If content is empty or first character is not `-` → return `{}`, content
     (genuine no-frontmatter; unchanged behavior).
   - If content starts with `-` but the first line is not exactly `---` →
     raise `MalformedFrontmatterError` naming `source_path` and the first line.
   - If content starts with `---` followed by `\n` or end-of-string → proceed
     with existing parsing logic (happy path unchanged).
4. Update `read_document` to pass `path` through to `_parse` as `source_path`.

**`clasi/project.py`**

1. Add three exception classes at module level:
   `SprintNotFoundError(ValueError)`, `SprintFrontmatterError(ValueError)`,
   `SprintIdMismatchError(ValueError)`.
2. Update `get_sprint`:
   - Wrap `read_frontmatter(sprint_file)` in
     `try/except MalformedFrontmatterError`; re-raise as
     `SprintFrontmatterError` with message naming the file and parse failure.
   - After reading frontmatter successfully: if `fm.get("id")` is falsy, raise
     `SprintIdMismatchError` naming the file and that `id` is absent.
   - If `fm.get("id") != sprint_id`, raise `SprintIdMismatchError` naming the
     file, the found id, and the requested id.
   - If no directory matched at all, raise `SprintNotFoundError` with the
     existing message.
3. Update `list_sprints`:
   - Wrap `read_frontmatter(sprint_file)` in `try/except
     MalformedFrontmatterError`; log `WARNING` naming the file and continue.

### Testing plan

File: `tests/test_frontmatter.py` (create or extend)

- `test_malformed_fence_raises`: write a temp file with `pwd---\nsome content`,
  call `read_frontmatter(path)`, assert `MalformedFrontmatterError` is raised
  and the message contains the file path.
- `test_no_frontmatter_returns_empty`: write a temp file with `# Just a body`,
  call `read_frontmatter(path)`, assert returns `{}`.
- `test_valid_frontmatter_parses`: write a temp file with `---\nid: "001"\n---\n`,
  assert returns `{"id": "001"}`.

File: `tests/test_project.py` (create or extend)

- `test_get_sprint_malformed_frontmatter_raises`: create a sprint dir with a
  corrupted `sprint.md`; call `project.get_sprint("001")`; assert
  `SprintFrontmatterError` raised and message names the file.
- `test_get_sprint_id_mismatch_raises`: sprint dir with valid frontmatter but
  `id: "999"`; call `project.get_sprint("001")`; assert `SprintIdMismatchError`.
- `test_get_sprint_not_found_raises`: no directories; call
  `project.get_sprint("001")`; assert `SprintNotFoundError`.
- `test_list_sprints_continues_past_corrupt_file`: two sprint dirs, one corrupt
  and one valid; call `project.list_sprints()`; assert only the valid sprint is
  returned and no exception propagates.

### Documentation updates

None required. These are internal implementation changes with no public API
surface.
