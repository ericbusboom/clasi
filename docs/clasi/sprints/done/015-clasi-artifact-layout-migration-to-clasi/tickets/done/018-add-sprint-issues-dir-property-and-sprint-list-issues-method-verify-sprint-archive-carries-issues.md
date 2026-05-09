---
id: 018
title: Add `Sprint.issues_dir` property and `Sprint.list_issues()` method; verify
  `Sprint.archive()` carries issues
status: done
use-cases:
  - SUC-002
depends-on:
  - "017"
github-issue: ''
todo: sprint-scoped-issues-directory.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add `Sprint.issues_dir` property and `Sprint.list_issues()` method; verify `Sprint.archive()` carries issues

## Description

Add two new members to the `Sprint` class in `clasi/sprint.py`:
- `Sprint.issues_dir` → property returning `self._path / "issues"`
- `Sprint.list_issues()` → method returning a list of `Issue` objects from
  `self.issues_dir.glob("*.md")`

Also verify (by test) that `Sprint.archive()` carries the `issues/` subdir to
`done/` automatically when the sprint directory moves. This should already be true
if `archive()` moves the entire sprint dir; confirm and add a test assertion.

## Acceptance Criteria

- [x] `Sprint.issues_dir` property returns `<sprint_path>/issues`
- [x] `Sprint.list_issues()` returns `Issue` objects for all files in `issues/`
- [x] Test: archive a sprint that has an `issues/` subdir; verify the issues dir is
  in `done/<sprint>/issues/` after archive
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/sprint.py` — add property and method

### Testing plan
- `uv run pytest tests/unit/test_sprint.py`
- New test for archive carrying issues
- `uv run pytest` — full suite
