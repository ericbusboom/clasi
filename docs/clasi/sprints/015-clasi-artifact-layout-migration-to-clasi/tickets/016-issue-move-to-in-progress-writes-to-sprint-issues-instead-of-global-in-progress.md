---
id: '016'
title: '`Issue.move_to_in_progress` writes to `<sprint>/issues/` instead of global
  `in-progress/`'
status: open
use-cases:
  - SUC-002
depends-on:
  - "006"
  - "003"
github-issue: ''
todo:
- move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
- sprint-scoped-issues-directory.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `Issue.move_to_in_progress` writes to `<sprint>/issues/` instead of global `in-progress/`

## Description

Change `Issue.move_to_in_progress(sprint_id, ticket_id)` so the issue file is moved to
`<sprint_dir>/issues/<filename>` instead of `<root>/issues/in-progress/<filename>`.

The sprint dir is resolved via `Project.get_sprint(sprint_id).path / "issues"`. The
`issues/` directory is created with `mkdir(parents=True, exist_ok=True)` if it does not
exist.

Frontmatter updates remain: `status: in-progress`, `sprint: <id>`, `ticket: <id>`.

## Acceptance Criteria

- [ ] After `move_to_in_progress`, the issue file is at `<sprint>/issues/<filename>`
- [ ] No file is created at `<root>/issues/in-progress/` or any global in-progress dir
- [ ] `<sprint>/issues/` is created automatically on first call
- [ ] Frontmatter: `status: in-progress`, correct sprint and ticket ids
- [ ] `tests/unit/test_issue_lifecycle.py` (or equivalent) verifies the new path
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/issue.py` — `move_to_in_progress` method
- Any callers in `clasi/tools/artifact_tools.py` that set the destination

### Testing plan
- `uv run pytest tests/unit/test_issue.py`
- New test: create issue → call move_to_in_progress with a mock sprint → assert file location
- `uv run pytest` — full suite
