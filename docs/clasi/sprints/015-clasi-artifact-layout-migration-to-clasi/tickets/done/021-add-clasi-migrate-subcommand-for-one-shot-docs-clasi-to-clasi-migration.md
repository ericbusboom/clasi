---
id: '021'
title: "Add clasi migrate subcommand for one-shot docs/clasi/ to .clasi/ migration"
status: done
use-cases:
  - SUC-001
depends-on:
  - "015"
  - "006"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add `clasi migrate` subcommand for one-shot `docs/clasi/` to `.clasi/` migration

## Description

Implement `clasi migrate` as a new CLI subcommand in `clasi/cli.py` (backed by
`clasi/migrate_command.py`). The subcommand migrates an existing project from the old
`docs/clasi/` layout to the new `.clasi/` layout.

Behavior:
1. Verify no execution lock is held for any active sprint.
2. Verify `.clasi/` does not already exist (guard against double-run).
3. `git mv docs/clasi .clasi` (falls back to `shutil.move` for non-git projects).
4. Update `.gitignore`: replace `docs/clasi/log/` entry with `.clasi/log/`.
5. Re-run `clasi install --force` to refresh rule files and agent prompts.
6. Print a prominent "restart any open CLASI sessions" notice.

## Acceptance Criteria

- [x] `clasi migrate` runs successfully on a project with `docs/clasi/`
- [x] After migration, `.clasi/` exists and `docs/clasi/` is gone
- [x] `.gitignore` has `.clasi/log/` (not `docs/clasi/log/`)
- [x] Guard: if `.clasi/` already exists, exits with a clear error
- [x] Guard: if an execution lock is held, exits with a clear error
- [x] Works for non-git projects (falls back to `shutil.move`)
- [x] Unit tests for `migrate_command.py` cover both git and non-git paths
- [x] Full test suite passes

## Implementation Plan

### Files to create/modify
- `clasi/migrate_command.py` — new module
- `clasi/cli.py` — wire `migrate` command group

### Testing plan
- Unit tests with a temp dir (git-initialized and plain)
- `uv run pytest tests/unit/test_migrate_command.py`
- `uv run pytest` — full suite
