---
id: '007'
title: Update `StateDB` path construction to use new `Project.clasi_dir`
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

# Update `StateDB` path construction to use new `Project.clasi_dir`

## Description

After ticket 006 changes `clasi_dir`, verify that the StateDB path (`Project.db`)
resolves correctly. The DB lives at `clasi_dir / ".clasi.db"`. If `state_db.py` or
`state_db_class.py` constructs paths independently (hardcoding `docs/clasi/`),
update them to use `Project.db` or `Project.clasi_dir`.

Also update any docstrings in `clasi/versioning.py` that reference `docs/clasi/settings.yaml`.

## Acceptance Criteria

- [ ] `Project.db` returns `<root>/.clasi/.clasi.db` (verified by test or inspection)
- [ ] `clasi/state_db.py` and `clasi/state_db_class.py` have no hardcoded `docs/clasi/` strings
- [ ] `clasi/versioning.py` docstrings updated if they reference old path
- [ ] Full test suite passes

## Implementation Plan

### Files to inspect and modify
- `clasi/project.py` — `db` property (should already be correct after ticket 006)
- `clasi/state_db.py` — check for hardcoded paths
- `clasi/state_db_class.py` — check for hardcoded paths
- `clasi/versioning.py` — docstring references

### Testing plan
- `uv run pytest tests/unit/test_state_db.py`
- `uv run pytest` — full suite
