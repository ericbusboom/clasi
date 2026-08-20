---
id: '006'
title: Atomic, line-anchored frontmatter I/O
status: done
use-cases:
- SUC-006
depends-on: []
github-issue: ''
issue: atomic-line-anchored-frontmatter-io.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Atomic, line-anchored frontmatter I/O

## Description

`frontmatter.py`'s body split uses `content.find("---", 3)`
(`frontmatter.py:79, 90`) — not line-anchored — so a `---` inside a
frontmatter value mis-slices the body, and the next round-trip write
persists the corruption. `_write_document` (`frontmatter.py:125-129`)
truncates in place with `path.write_text(...)`; a crash mid-write
corrupts the file, which then raises `MalformedFrontmatterError` and
`list_sprints` silently drops the sprint. `yaml.dump` (line 127) should
be `yaml.safe_dump`.

**Scope**: `src/clasi/frontmatter.py` only.

**Files to touch (verified during planning):**

- `frontmatter.py:79, 90` (`_parse`) — replace `content.find("---", 3)`
  with a line-anchored search (matching only a line that is exactly
  `---`, not any occurrence of the substring), or delegate to
  `python-frontmatter`'s own serializer if that's already a project
  dependency (verify before choosing this path).
- `frontmatter.py:125-129` (`_write_document`) — write to a temp file
  (e.g. `path.with_suffix(path.suffix + ".tmp")`, or `tempfile` in the
  same directory to guarantee same-filesystem atomicity) and
  `os.replace()` it over `path`, instead of `path.write_text(content,
  encoding="utf-8")` directly.
- `frontmatter.py:127` — `yaml.dump(...)` → `yaml.safe_dump(...)`.

## Acceptance Criteria

- [x] Frontmatter delimiter detection is line-anchored (or delegated to
      the `python-frontmatter` serializer)
- [x] All artifact writes go through temp-file + `os.replace`
- [x] A round-trip test with a `---` inside a frontmatter value (e.g. a
      `notes:` field containing a line that is exactly `---`) passes
- [x] A malformed file surfaces a loud, named error where it is read —
      not a silent drop from `list_sprints`/listings (verify the
      existing `MalformedFrontmatterError` path still fires and is not
      swallowed anywhere new)
- [x] `yaml.safe_dump` replaces `yaml.dump`

## Implementation Notes

- Line anchoring: `_parse` now delegates the body-start search to a new
  `_find_body_start` helper that walks `content.splitlines(keepends=True)`
  line by line (after the opening fence) and only matches a line whose
  `rstrip("\r\n")` is exactly `---`. An indented occurrence (e.g. the
  `  ---` line `yaml.safe_dump` produces inside a folded/quoted multi-line
  scalar) no longer false-positives, since indentation is not stripped
  before the equality check.
- Atomic write: `_write_document` now writes to a `tempfile.mkstemp`-created
  file in `path.parent` (guaranteeing same-filesystem `os.replace`),
  fsyncs before replacing, copies the destination's existing permission
  bits onto the temp file first (a bare `os.replace` would otherwise hand
  the file the temp file's umask-derived mode), and unlinks the temp file
  on any exception so a crash mid-write leaves the original completely
  untouched.
- `yaml.dump` → `yaml.safe_dump` in `_write_document` only (scope is
  `frontmatter.py`; other `yaml.dump` call sites in `dispatch_log.py`,
  `platforms/copilot.py`, `status/formatting.py` are out of scope for
  this ticket).
- Malformed-file surfacing: left `Project.list_sprints` (project.py)
  unchanged — it's out of this ticket's scope (`frontmatter.py` only)
  and its existing behavior already matches the acceptance criterion's
  own fallback clause: it catches `MalformedFrontmatterError` and logs a
  warning with both the path and the exception's reason, then skips that
  one sprint while keeping the rest of the listing functional. The
  "loud, named error at the read site" requirement is met by
  `Project.get_sprint` (project.py), which reads a single sprint by id
  and re-raises as `SprintFrontmatterError` — already covered by
  `tests/unit/test_project.py::TestGetSprintTypedExceptions`, which
  still passes unchanged. Ran both
  `test_project.py::TestGetSprintTypedExceptions` and
  `test_project.py::TestListSprintsCorruptFile` after the frontmatter.py
  changes to confirm neither behavior regressed.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_frontmatter.py tests/unit/test_frontmatter_tools.py`
  (scoped, foreground)
- **New tests to write**: the `---`-inside-a-value round-trip test
  above; a simulated mid-write crash (e.g. monkeypatch `os.replace` to
  raise after the temp file is written, assert the original file is
  untouched); a `yaml.safe_dump` regression test (dumping a non-safe
  type should raise, matching `safe_dump`'s stricter behavior).
- **Verification command**: `uv run pytest tests/unit/test_frontmatter.py tests/unit/test_frontmatter_tools.py -v`
