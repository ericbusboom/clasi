---
status: in-progress
type: bug
tags:
- reliability-campaign
- phase-1
- artifacts
sprint: 029
tickets:
- 029-006
---

# Frontmatter I/O: line-anchored parsing and atomic writes

## Description

Two related corruption paths in `src/clasi/frontmatter.py`, from the
reliability review (01-state-layer.md finding 12; 02-mcp-tools.md F11):

1. The body split uses `content.find("---", 3)` — not line-anchored — so a
   `---` inside a frontmatter value mis-slices the body, and the next
   `update_frontmatter` round-trip writes the corruption back.
2. `_write_document` truncates in place with `write_text`; a crash mid-write
   corrupts the file, which then raises `MalformedFrontmatterError` — and
   `list_sprints` silently drops the sprint (`project.py:416`).

Also use `yaml.safe_dump` rather than `yaml.dump`.

## Acceptance criteria

- Frontmatter delimiter detection is line-anchored (or delegated to the
  `python-frontmatter` serializer).
- All artifact writes go through temp-file + `os.replace`.
- A round-trip test with a `---` inside a frontmatter value passes.
- A malformed file surfaces a loud, named error where it is read — not a
  silent drop from listings.
