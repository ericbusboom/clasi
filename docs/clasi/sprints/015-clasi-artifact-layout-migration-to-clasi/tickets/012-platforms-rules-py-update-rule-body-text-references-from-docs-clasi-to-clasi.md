---
id: '012'
title: '`platforms/_rules.py`: update rule body text references from `docs/clasi/`
  to `.clasi/`'
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

# `platforms/_rules.py`: update rule body text references from `docs/clasi/` to `.clasi/`

## Description

Update `clasi/platforms/_rules.py` — the rule body prose (not frontmatter globs; those
are in tickets 009-011). The rule bodies contain references to `docs/clasi/oop` (OOP
override path) and `docs/clasi/sprints/` in the text agents read at runtime.

Also update the `.gitignore` template if it lives in `_rules.py` or a sibling file
(replace `docs/clasi/log/` with `.clasi/log/`).

## Acceptance Criteria

- [ ] Rule body text: `docs/clasi/oop` → `.clasi/oop`
- [ ] Rule body text: `docs/clasi/sprints/` → `.clasi/sprints/`
- [ ] `.gitignore` template updated: `docs/clasi/log/` → `.clasi/log/`
- [ ] No `docs/clasi` prose references remain in `_rules.py`
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/platforms/_rules.py` — rule body string literals
- Any gitignore template file that references old paths

### Testing plan
- `uv run pytest tests/unit/` — rule content is tested indirectly via install tests
- `uv run pytest` — full suite
