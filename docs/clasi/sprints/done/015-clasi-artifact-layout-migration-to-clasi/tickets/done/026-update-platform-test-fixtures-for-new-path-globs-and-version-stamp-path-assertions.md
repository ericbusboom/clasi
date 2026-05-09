---
id: "026"
title: "Update platform test fixtures for new path globs and version stamp path assertions"
status: done
use-cases:
  - SUC-001
depends-on:
  - "009"
  - "010"
  - "011"
  - "020"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update platform test fixtures for new path globs and version stamp path assertions

## Description

Update platform-specific test files for the new path layout and version stamp:
- `tests/unit/test_platform_claude.py` — path glob assertions, no `docs/clasi`
- `tests/unit/test_platform_codex.py` (29 occurrences!) — path strings, AGENTS.md content
- `tests/unit/test_platform_copilot.py` — path glob assertions
- `tests/unit/test_three_platform_install.py` — integration test path assertions
- `tests/unit/test_uninstall_command.py` — uninstall path assertions
- Version stamp path: assertions checking `.claude/.clasi-version` change to
  `.clasi/clasi-version`

## Acceptance Criteria

- [x] No `docs/clasi` string literals in any platform test file
- [x] Version stamp assertions check `.clasi/clasi-version` not per-platform stamp paths
- [x] All platform tests pass
- [x] `uv run pytest tests/unit/test_platform_*.py tests/unit/test_three_platform_install.py
  tests/unit/test_uninstall_command.py` — green
- [x] `uv run pytest` — full suite

## Implementation Plan

### Files to modify
- `tests/unit/test_platform_claude.py`
- `tests/unit/test_platform_codex.py`
- `tests/unit/test_platform_copilot.py`
- `tests/unit/test_three_platform_install.py`
- `tests/unit/test_uninstall_command.py`
- `tests/clasr/test_platform_codex.py` (6 occurrences)

### Testing plan
- `uv run pytest tests/unit/test_platform_*.py`
- `uv run pytest` — full suite
