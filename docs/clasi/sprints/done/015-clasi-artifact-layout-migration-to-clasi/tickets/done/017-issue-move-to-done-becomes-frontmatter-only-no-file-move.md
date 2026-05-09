---
id: '017'
title: '`Issue.move_to_done` becomes frontmatter-only (no file move)'
status: done
use-cases:
  - SUC-002
depends-on:
  - "016"
github-issue: ''
todo: sprint-scoped-issues-directory.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `Issue.move_to_done` becomes frontmatter-only (no file move)

## Description

Remove the file-move logic from `Issue.move_to_done`. After this ticket, calling
`move_to_done` only updates the frontmatter (`status: done`, `tickets:` list) and
leaves the file in place at `<sprint>/issues/<filename>`. The sprint's `archive()`
operation (on `close_sprint`) is responsible for physically relocating the sprint
directory (and thus its `issues/` subdir) to `done/`.

Also update `clasi/tools/artifact_tools.py`'s `move_issue_to_done` (formerly
`move_todo_to_done`) to validate that the issue is in `<sprint_id>/issues/` before
calling `move_to_done`.

## Acceptance Criteria

- [x] `Issue.move_to_done` only writes frontmatter: `status: done`, `tickets:` list
- [x] No file is moved or renamed in `move_to_done`
- [x] The issue file stays at `<sprint>/issues/<filename>` after `move_to_done`
- [x] `artifact_tools.py` validates the issue is in the correct sprint's `issues/` dir
- [x] Tests verify: file location unchanged after done; `status: done` in frontmatter
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/issue.py` — `move_to_done` method: remove `shutil.move`; keep frontmatter write
- `clasi/tools/artifact_tools.py` — validation logic

### Testing plan
- `uv run pytest tests/unit/test_issue.py`
- New test: move_to_done does not change file location
- `uv run pytest` — full suite
