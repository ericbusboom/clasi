---
id: '013'
title: 'CLI: rename `plan-to-todo` subcommand to `plan-to-issue` and `--todo-dir`
  to `--issues-dir`'
status: open
use-cases:
  - SUC-001
depends-on:
  - "004"
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# CLI: rename `plan-to-todo` subcommand to `plan-to-issue` and `--todo-dir` to `--issues-dir`

## Description

In `clasi/cli.py`, rename the CLI subcommand and its options. Also update the
`install_hooks` call that registers hook names (they must match the handler names
from ticket 008).

## Acceptance Criteria

- [ ] `@tool.command("plan-to-todo")` renamed to `@tool.command("plan-to-issue")`
- [ ] `--todo-dir` option renamed to `--issues-dir`
- [ ] Default value for `--issues-dir` updated to `".clasi/issues"`
- [ ] Help strings updated to use "issue" language
- [ ] Hook registration keys updated to `"plan-to-issue"` and `"codex-plan-to-issue"`
- [ ] `clasi tool plan-to-issue --help` works correctly
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/cli.py` — subcommand decorator, option names, help strings, hook registration

### Testing plan
- `uv run pytest tests/unit/test_cli.py` (if exists)
- Test manually: `clasi tool plan-to-issue --help`
- `uv run pytest` — full suite
