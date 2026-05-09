---
id: 009
title: '`platforms/claude.py`: update path globs and rule frontmatter for `.clasi/`
  and `.clasi/issues/`'
status: done
use-cases:
  - SUC-001
depends-on:
  - "006"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `platforms/claude.py`: update path globs and rule frontmatter for `.clasi/` and `.clasi/issues/`

## Description

Update `clasi/platforms/claude.py` to replace all `docs/clasi/` path references in:
- YAML frontmatter `paths:` globs for rule files (e.g. `paths: ["docs/clasi/**"]`)
- The `paths:` glob for the issues/todo rule (e.g. `paths: ["docs/clasi/todo/**"]`)

These globs scope which files trigger which rule files for the Claude platform.

## Acceptance Criteria

- [x] `paths: ["docs/clasi/**"]` changed to `paths: [".clasi/**"]` in all rule definitions
- [x] `paths: ["docs/clasi/todo/**"]` changed to `paths: [".clasi/issues/**"]`
- [x] No `docs/clasi` string literals remain in `claude.py`
- [x] `tests/unit/test_platform_claude.py` assertions updated (full in ticket 026)
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/platforms/claude.py` — YAML frontmatter glob strings in rule definitions

### Testing plan
- `uv run pytest tests/unit/test_platform_claude.py`
- `uv run pytest` — full suite
