---
id: "002"
title: "Update sprint.md template to set status: roadmap in frontmatter"
status: todo
use-cases:
  - SUC-001
depends-on:
  - 017-001
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint.md template to set status: roadmap in frontmatter

## Description

The sprint.md template at `clasi/templates/sprint.md` generates the initial
`sprint.md` file when `create_sprint` is called. Currently the `status` field
in the template frontmatter is not `roadmap`. This ticket changes it so every
sprint created from the template starts in `status: roadmap`.

No structural changes to the template body or other placeholders.

**Files to modify:**
- `clasi/templates/sprint.md`: set `status: roadmap` in frontmatter.

## Acceptance Criteria

- [ ] `clasi/templates/sprint.md` frontmatter contains `status: roadmap`.
- [ ] All existing template placeholders (`{id}`, `{title}`, `{slug}`) remain intact and functional.
- [ ] `uv run pytest` passes with no regressions.

## Implementation Plan

- Read `clasi/templates/sprint.md`.
- Edit the `status:` line in the YAML frontmatter to read `status: roadmap`.
- No other changes.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: Covered in ticket 009 (`test_create_sprint_status_roadmap`).
- **Verification command**: `uv run pytest`
