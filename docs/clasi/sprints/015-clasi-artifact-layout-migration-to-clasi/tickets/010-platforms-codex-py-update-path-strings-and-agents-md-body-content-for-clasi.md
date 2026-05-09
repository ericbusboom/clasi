---
id: '010'
title: '`platforms/codex.py`: update path strings and AGENTS.md body content for `.clasi/`'
status: todo
use-cases:
  - SUC-001
depends-on:
  - "006"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `platforms/codex.py`: update path strings and AGENTS.md body content for `.clasi/`

## Description

Update `clasi/platforms/codex.py` to replace all `docs/clasi/` path references in:
- `_build_clasi_dir_content()` — the AGENTS.md body text that instructs Codex agents
  where CLASI artifacts live
- `_build_issues_dir_content()` (was `_build_todo_dir_content()`) — the issues dir
  AGENTS.md body
- `_install_rules` / `_uninstall_rules` — nested AGENTS.md targets at
  `target/.clasi/AGENTS.md` and `target/.clasi/issues/AGENTS.md`
- Function names: `_build_todo_dir_content` → `_build_issues_dir_content`

## Acceptance Criteria

- [ ] No `docs/clasi` string literals remain in `codex.py`
- [ ] Nested AGENTS.md files installed at `.clasi/AGENTS.md` and `.clasi/issues/AGENTS.md`
- [ ] `_build_todo_dir_content` renamed to `_build_issues_dir_content`
- [ ] Body text in these functions updated to reference `.clasi/` paths
- [ ] `tests/unit/test_platform_codex.py` assertions updated (full in ticket 026)
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/platforms/codex.py` — path strings, function names, body text

### Testing plan
- `uv run pytest tests/unit/test_platform_codex.py`
- `uv run pytest` — full suite
