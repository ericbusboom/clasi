---
status: in-progress
sprint: '017'
tickets:
- 017-001
- 017-002
---

# Migration leaves empty source directories behind after relocating artifacts

## Context

When `clasi init` (or `clasi migrate`) detects misplaced artifacts and moves them to the
new layout — e.g. `.clasi/architecture` → `docs/architecture`, `.clasi/issues` → `clasi/issues`,
`.clasi/design` → `docs/design` — the **files** are relocated correctly, but the now-empty
**source directories are left behind** (each containing a stray `.gitkeep`). The user sees
leftover `.clasi/architecture/`, `.clasi/issues/`, etc. after a migration that was supposed
to vacate them. The migration should remove the emptied source directories.

## Root cause (a four-step chain — all in the new `src/` layout)

1. **`init` scaffolds the destinations first, with `.gitkeep`.** [src/clasi/init_command.py:207-220](src/clasi/init_command.py#L207-L220) iterates `ARTIFACT_PATH_DEFAULTS` and creates every destination dir (`clasi/issues`, `docs/architecture`, …) with a `.gitkeep` — *before* the relocation prompt runs (`detect_moves` is called right after, ~lines 241-245).
2. **A non-empty destination forces "merge" mode.** [src/clasi/migrate_command.py:250-256](src/clasi/migrate_command.py#L250-L256): `mode = "merge" if (dst.exists() and any(dst.iterdir())) else "move"`. Because the dest was just scaffolded and contains `.gitkeep`, `any(dst.iterdir())` is true → **merge** (file-by-file) instead of **move** (whole-dir rename).
3. **Merge moves only real files; `.gitkeep` stays in the source.** [src/clasi/migrate_command.py:352-371](src/clasi/migrate_command.py#L352-L371) loops `src.rglob("*")` and moves `is_file()` artifacts; `.gitkeep` is in `_NON_ARTIFACT_NAMES` ([:77](src/clasi/migrate_command.py#L77)) and is never moved, so it remains in the source dir.
4. **Cleanup can't remove a non-empty dir.** After the merge, [migrate_command.py:371](src/clasi/migrate_command.py#L371) calls `_cleanup_empty_parents(src, root)` ([:163-177](src/clasi/migrate_command.py#L163-L177)), which `rmdir`s only while empty. The leftover `.gitkeep` makes `rmdir` raise `OSError` → it breaks → **source dir survives with a stray `.gitkeep`.**

So the cleanup logic itself is fine; the emptied source dir is stranded by a `.gitkeep` that the merge intentionally leaves behind (compounded by `init` pre-creating the destinations, which forces merge mode in the first place).

## Suggested fix

Make the relocation vacate the source dir even in merge mode. Either (or both):

- **Drop non-artifact files (`.gitkeep`/`.gitignore`) from the SOURCE before cleanup** in the merge branch of `execute_moves`, so `_cleanup_empty_parents(src)` succeeds. (Smallest, most direct fix.)
- **Treat an all-`.gitkeep` destination as effectively empty for mode selection** in `detect_moves` (so a freshly-scaffolded dest yields `mode="move"`, a clean whole-dir rename, with no leftover) — and drop the dest's stray `.gitkeep` on move-in. (This was an explicitly-noted design intent in Sprint 013 that wasn't implemented.)

Keep the no-clobber guarantee for real files. The `.clasi/` root itself must stay (it retains `config.yaml`, `log/`, `.clasi.db`) — only the moved-from category subdirs should be removed.

## Affected files

- [src/clasi/migrate_command.py](src/clasi/migrate_command.py) — `detect_moves` mode decision (~250-256), the merge branch + cleanup call in `execute_moves` (~352-371), `_cleanup_empty_parents` (~163-177).
- [src/clasi/init_command.py](src/clasi/init_command.py) — scaffold-before-detect ordering (~207-245); optionally detect/move before scaffolding remaining dirs.
- Tests: [tests/unit/test_migrate_command.py](tests/unit/test_migrate_command.py) and [tests/unit/test_relocate.py](tests/unit/test_relocate.py) — existing tests at ~384-450 allow the source dir to remain as long as it has no artifact files; they don't assert full removal.

## Acceptance criteria

- After `clasi init` / `clasi migrate` relocates a category, the source directory (e.g. `.clasi/architecture`, `.clasi/issues`) **no longer exists** — not merely empty-of-artifacts.
- Works in the realistic scenario where `init` has pre-created the destination dirs with `.gitkeep` (i.e. merge mode), not just the clean move-mode case.
- No real (artifact) files are clobbered; `.clasi/` itself and its retained state (`config.yaml`, `log/`, `.clasi.db`) are untouched.
- A regression test seeds a legacy `.clasi/<category>` with a real file, pre-creates the destination with `.gitkeep` (as `init` does), runs the migration, and asserts the source dir is gone.

## Verification

1. Scratch repo: create `.clasi/architecture/arch.md` and `.clasi/issues/x.md`; run `clasi init --yes` (or `clasi migrate --yes`); confirm files landed in `docs/architecture`/`clasi/issues` AND `.clasi/architecture`/`.clasi/issues` are gone (`.clasi/` keeps only `config.yaml`, `log/`, `.clasi.db`).
2. `uv run pytest tests/unit/test_migrate_command.py tests/unit/test_relocate.py -q` — including the new source-dir-removal regression test — passes.
