---
id: '001'
title: Fix merge-mode source directory cleanup in migrate_command
status: in-progress
use-cases:
- SUC-017-001
- SUC-017-002
depends-on: []
github-issue: ''
issue: migration-leaves-empty-source-directories-behind-after-relocating-artifacts.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix merge-mode source directory cleanup in migrate_command

## Description

`clasi init` / `clasi migrate` leaves source category directories (e.g.
`.clasi/issues/`, `.clasi/architecture/`) behind after relocating their
artifacts. The root cause is a two-part bug in `src/clasi/migrate_command.py`:

1. **`detect_moves` mode decision** (~line 254): `any(dst.iterdir())` returns
   True when the destination contains only a `.gitkeep` (placed there by
   `init`'s scaffold step), forcing `mode="merge"` unnecessarily.

2. **Merge-branch cleanup**: after moving all real artifact files, `.gitkeep`
   remains in the source directory. `_cleanup_empty_parents` then cannot
   `rmdir` the source because it is non-empty.

This ticket applies both fixes to `src/clasi/migrate_command.py`:

- Fix 1 (`detect_moves`): filter `dst.iterdir()` through `_NON_ARTIFACT_NAMES`
  before deciding "non-empty", mirroring the existing source-side check.
- Fix 2 (`execute_moves` merge branch): after the real-file move loop, unlink
  any remaining files whose names are in `_NON_ARTIFACT_NAMES` from the source
  tree, so `_cleanup_empty_parents` can `rmdir` successfully.

## Acceptance Criteria

- [ ] In `detect_moves`, a destination directory containing only `.gitkeep`
      causes `mode="move"` to be returned (not `mode="merge"`).
- [ ] In `detect_moves`, a destination directory containing at least one real
      artifact file still causes `mode="merge"` (no-clobber guarantee
      preserved).
- [ ] In `execute_moves` merge branch, after moving real artifact files, any
      `.gitkeep` or `.gitignore` files remaining in the source tree are deleted
      with `unlink()`.
- [ ] `_cleanup_empty_parents` is called unchanged; no modifications to that
      function.
- [ ] No real artifact files are deleted or clobbered by either fix.
- [ ] All existing tests in `tests/unit/test_migrate_command.py` and
      `tests/unit/test_relocate.py` pass without modification.

## Implementation Plan

### Approach

Two surgical edits, both in `src/clasi/migrate_command.py`. No other files
change. No new imports needed (`_NON_ARTIFACT_NAMES` is already module-level).

### Files to Modify

- `src/clasi/migrate_command.py`

### Fix 1 — detect_moves mode selection

Locate the mode decision block (~line 250-254):

```python
        # Determine mode.
        if is_file:
            mode = "merge" if dst.exists() else "move"
        else:
            mode = "merge" if (dst.exists() and any(dst.iterdir())) else "move"
```

Replace the `else` branch with a filtered check:

```python
        # Determine mode.
        if is_file:
            mode = "merge" if dst.exists() else "move"
        else:
            dst_artifact_files = (
                [f for f in dst.iterdir() if f.name not in _NON_ARTIFACT_NAMES]
                if dst.exists()
                else []
            )
            mode = "merge" if dst_artifact_files else "move"
```

This treats a destination containing only `.gitkeep` / `.gitignore` as
effectively empty (same logic as the source-side `artifact_files` check at
~line 226-229).

### Fix 2 — execute_moves merge branch cleanup

Locate the merge branch in `execute_moves` (~lines 352-371). After the
per-file move loop and before the `_cleanup_empty_parents` call, insert:

```python
            # Remove residual non-artifact files (e.g. .gitkeep) so that
            # _cleanup_empty_parents can rmdir the source directory.
            for item in sorted(src.rglob("*")):
                if item.is_file() and item.name in _NON_ARTIFACT_NAMES:
                    item.unlink()
            # Clean up (now potentially empty) source tree.
            _cleanup_empty_parents(src, root)
```

### Testing Plan

Run after making the changes:

```
uv run pytest tests/unit/test_migrate_command.py tests/unit/test_relocate.py -v
```

All existing tests must pass. The new regression tests (ticket 002) exercise
the bug scenario end-to-end and must also pass.

### Documentation Updates

No documentation updates required. The `architecture-update.md` for this
sprint is the design record.
