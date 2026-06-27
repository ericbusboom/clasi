---
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 017 Use Cases

## SUC-017-001: Migrate fully removes source category directory in merge mode

- **Actor**: Developer running `clasi init --yes` or `clasi migrate --yes`
- **Preconditions**:
  - A legacy source category directory exists (e.g. `.clasi/issues/`) containing
    at least one real artifact file (e.g. `idea.md`).
  - The configured destination directory (e.g. `clasi/issues/`) already exists
    and contains only a `.gitkeep` (as created by `clasi init` scaffold step).
  - `detect_moves` therefore selects `mode="merge"` for this category.
- **Main Flow**:
  1. `clasi init --yes` (or `clasi migrate --yes`) runs.
  2. `detect_moves` detects the source as non-empty and the destination as
     pre-scaffolded.
  3. `execute_moves` runs the merge branch: moves real artifact files from
     source to destination (no clobber).
  4. Any residual non-artifact files (`.gitkeep`) are removed from the source
     directory.
  5. `_cleanup_empty_parents` successfully `rmdir`s the now-truly-empty source
     directory (and any empty ancestors up to `.clasi/`).
- **Postconditions**:
  - All real artifact files are present in the destination directory.
  - The source category directory no longer exists on disk.
  - `.clasi/` root is intact (`config.yaml`, `log/`, `.clasi.db` untouched).
  - No real artifact files were clobbered.
- **Acceptance Criteria**:
  - [ ] Source category directory (e.g. `.clasi/issues/`) does not exist after
        migration.
  - [ ] Real artifact files land in the destination directory unchanged.
  - [ ] Files already present in the destination are not overwritten.
  - [ ] `.clasi/` root directory and its non-category contents survive.

## SUC-017-002: Detect-moves treats all-non-artifact destination as effectively empty

- **Actor**: `detect_moves` logic (internal, exercised by both `init` and `migrate`)
- **Preconditions**:
  - A source category directory contains real artifact files.
  - The destination directory exists and contains ONLY non-artifact files
    (`.gitkeep` and/or `.gitignore`).
- **Main Flow**:
  1. `detect_moves` iterates candidate locations and finds the source.
  2. For the mode decision, it checks whether the destination has any real
     (artifact) files — not whether `any(dst.iterdir())` is truthy.
  3. Because the destination contains only `.gitkeep`, it is treated as
     effectively empty.
  4. `mode="move"` is selected: the source directory is renamed wholesale to
     the destination, no residual files remain in source.
- **Postconditions**:
  - The returned `Move` object has `mode="move"` rather than `mode="merge"`.
  - `execute_moves` can perform a clean directory rename (no per-file loop).
  - The source directory is guaranteed gone after `_cleanup_empty_parents`.
- **Acceptance Criteria**:
  - [ ] A destination containing only `.gitkeep` causes `mode="move"` to be
        selected (not `mode="merge"`).
  - [ ] A destination containing at least one real artifact file still causes
        `mode="merge"` (no-clobber guarantee preserved).
  - [ ] Existing unit tests continue to pass.
