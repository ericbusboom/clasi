---
id: '011'
title: '`platforms/copilot.py`: update instruction path globs for `.clasi/` and `.clasi/issues/`'
status: open
use-cases:
  - SUC-001
depends-on:
  - "006"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `platforms/copilot.py`: update instruction path globs for `.clasi/` and `.clasi/issues/`

## Description

Update `clasi/platforms/copilot.py` to replace all `docs/clasi/` path references in:
- Path-rule tuples that define the `applyTo` glob for Copilot instruction files
  (e.g. `("clasi-artifacts.instructions.md", "docs/clasi/**", ...)`)
- Issues/todo path glob: `"docs/clasi/todo/**"` → `".clasi/issues/**"`

## Acceptance Criteria

- [ ] `"docs/clasi/**"` changed to `".clasi/**"` in all path-rule tuples
- [ ] `"docs/clasi/todo/**"` changed to `".clasi/issues/**"`
- [ ] No `docs/clasi` string literals remain in `copilot.py`
- [ ] `tests/unit/test_platform_copilot.py` assertions updated (full in ticket 026)
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/platforms/copilot.py` — path glob strings

### Testing plan
- `uv run pytest tests/unit/test_platform_copilot.py`
- `uv run pytest` — full suite
