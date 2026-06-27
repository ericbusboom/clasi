---
id: '017'
title: Fix migration leaving empty source directories
status: done
branch: sprint/017-fix-migration-leaving-empty-source-directories
use-cases:
- SUC-017-001
- SUC-017-002
issues:
- migration-leaves-empty-source-directories-behind-after-relocating-artifacts.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 017: Fix migration leaving empty source directories

## Goals

Ensure that `clasi init` / `clasi migrate` fully removes the source category
directories (e.g. `.clasi/architecture/`, `.clasi/issues/`) after relocating
their artifacts, even when the destination was pre-scaffolded with a `.gitkeep`
(which forces merge mode and currently strands a `.gitkeep` in the source).

## Problem

The migration pipeline has a four-step bug chain:

1. `init_command.py` scaffolds every destination directory with `.gitkeep`
   before `detect_moves` runs.
2. A destination that contains `.gitkeep` is "non-empty", so `detect_moves`
   picks `mode="merge"` instead of `mode="move"`.
3. The merge branch of `execute_moves` skips files whose names are in
   `_NON_ARTIFACT_NAMES` (which includes `.gitkeep`), so `.gitkeep` stays
   behind in the source directory.
4. `_cleanup_empty_parents(src)` calls `rmdir` on the source, which raises
   `OSError` because the leftover `.gitkeep` makes the directory non-empty.
   The source directory survives.

## Solution

Apply two complementary fixes in `migrate_command.py`:

1. **`detect_moves` mode decision** (~line 254): treat a destination that
   contains ONLY non-artifact files (`.gitkeep`, `.gitignore`) as effectively
   empty — choose `mode="move"` so the whole directory is renamed cleanly.
2. **Merge-branch cleanup** (execute_moves merge branch, ~line 371): after
   moving all real artifact files, explicitly delete any remaining non-artifact
   files (`.gitkeep`, `.gitignore`) from the source directory so that
   `_cleanup_empty_parents` can `rmdir` it successfully.

Both fixes are defensive and independent. Fix 1 handles the init-scaffolded
case optimally (clean move). Fix 2 is a safety net that handles residual
non-artifact files left in the source after any merge.

## Success Criteria

- After `clasi init --yes` or `clasi migrate --yes`, source category
  directories (`.clasi/architecture`, `.clasi/issues`, etc.) are completely
  gone — not merely empty-of-artifacts.
- The fix works in the realistic scenario where init has pre-created
  destination dirs with `.gitkeep` (merge mode path).
- No real artifact files are clobbered.
- `.clasi/` root itself is untouched (retains `config.yaml`, `log/`,
  `.clasi.db`).
- A new regression test confirms source-dir-removal in the merge-mode scenario.

## Scope

### In Scope

- Fix `detect_moves` mode selection to treat all-non-artifact destinations as
  effectively empty (choose `mode="move"`).
- Fix merge-branch cleanup in `execute_moves` to delete residual non-artifact
  files from the source before calling `_cleanup_empty_parents`.
- Add a regression test seeding `.clasi/<category>` with a real file,
  pre-creating the destination with `.gitkeep`, running migration, and
  asserting the source directory is gone.
- Tighten the existing weak assertion in `test_file_moved_to_destination` from
  "empty-or-non-existent" to `not src_dir.exists()`.

### Out of Scope

- Reordering scaffold-before-detect in `init_command.py`.
- Refactoring `_cleanup_empty_parents` internals.
- Migration behavior for any category other than the directory case.

## Test Strategy

Unit tests under `tests/unit/test_migrate_command.py`:
- New test class `TestMergeModeCleansUpSourceDir` with a scenario that exactly
  mirrors the bug: legacy source has a real file, destination is pre-created
  with only a `.gitkeep`, run `detect_moves` + `execute_moves`, assert
  `src_dir.exists()` is False.
- Tighten the existing weak assertion in `test_file_moved_to_destination`.

Run with: `uv run pytest tests/unit/test_migrate_command.py tests/unit/test_relocate.py -q`

## Architecture Notes

All changes are confined to `src/clasi/migrate_command.py`. The two touch
points are the mode-selection expression in `detect_moves` and the
post-move cleanup section in the merge branch of `execute_moves`. No new
modules, no interface changes, no schema changes.

## GitHub Issues

None.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Fix merge-mode source directory cleanup in migrate_command | — |
| 002 | Regression tests for source-directory removal after merge-mode migration | 001 |

Tickets execute serially in the order listed.
