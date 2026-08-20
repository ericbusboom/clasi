---
id: '006'
title: Atomic, line-anchored frontmatter I/O
status: open
use-cases: [SUC-006]
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

- [ ] Frontmatter delimiter detection is line-anchored (or delegated to
      the `python-frontmatter` serializer)
- [ ] All artifact writes go through temp-file + `os.replace`
- [ ] A round-trip test with a `---` inside a frontmatter value (e.g. a
      `notes:` field containing a line that is exactly `---`) passes
- [ ] A malformed file surfaces a loud, named error where it is read —
      not a silent drop from `list_sprints`/listings (verify the
      existing `MalformedFrontmatterError` path still fires and is not
      swallowed anywhere new)
- [ ] `yaml.safe_dump` replaces `yaml.dump`

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_frontmatter.py tests/unit/test_frontmatter_tools.py`
  (scoped, foreground)
- **New tests to write**: the `---`-inside-a-value round-trip test
  above; a simulated mid-write crash (e.g. monkeypatch `os.replace` to
  raise after the temp file is written, assert the original file is
  untouched); a `yaml.safe_dump` regression test (dumping a non-safe
  type should raise, matching `safe_dump`'s stricter behavior).
- **Verification command**: `uv run pytest tests/unit/test_frontmatter.py tests/unit/test_frontmatter_tools.py -v`
