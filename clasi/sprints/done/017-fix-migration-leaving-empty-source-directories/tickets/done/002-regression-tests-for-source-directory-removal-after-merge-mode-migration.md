---
id: '002'
title: Regression tests for source-directory removal after merge-mode migration
status: done
use-cases:
- SUC-017-001
- SUC-017-002
depends-on:
- '001'
github-issue: ''
issue: migration-leaves-empty-source-directories-behind-after-relocating-artifacts.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Regression tests for source-directory removal after merge-mode migration

## Description

After the fixes in ticket 001, add regression tests that codify the correct
behavior and guard against future regressions. The key test scenario mirrors
the exact bug chain:

1. A legacy source directory (`.clasi/issues/`) contains a real artifact file.
2. The destination (`clasi/issues/`) already exists with only a `.gitkeep`
   (as `clasi init` would create it).
3. `detect_moves` + `execute_moves` run.
4. Assert the source directory is gone entirely (`not src_dir.exists()`).

Also tighten the existing weak assertion in `test_file_moved_to_destination`
which currently allows the source dir to survive as long as it is empty-of-
artifacts (`not any(src_dir.iterdir())`); it should now assert `not
src_dir.exists()`.

## Acceptance Criteria

- [x] A new test class `TestMergeModeCleansUpSourceDir` exists in
      `tests/unit/test_migrate_command.py`.
- [x] Test `test_source_dir_removed_when_dest_has_only_gitkeep`: seeds
      `.clasi/issues/` with `idea.md`, pre-creates `clasi/issues/.gitkeep`,
      runs `detect_moves` + `execute_moves`, asserts `src_dir.exists()` is
      False.
- [x] Test `test_detect_moves_treats_gitkeep_only_dest_as_move_mode`:
      verifies `detect_moves` returns `mode="move"` (not `mode="merge"`) when
      destination contains only `.gitkeep`.
- [x] Test `test_no_clobber_preserved_in_merge_with_real_dst_file`: seeds
      `.clasi/issues/conflict.md` and `clasi/issues/conflict.md` (both real
      files), verifies `detect_moves` still returns `mode="merge"` and the
      existing destination file is not overwritten.
- [x] The existing test `test_file_moved_to_destination` is updated: replace
      `not src_dir.exists() or not any(src_dir.iterdir())` with
      `not src_dir.exists()`.
- [x] `uv run pytest tests/unit/test_migrate_command.py tests/unit/test_relocate.py -q`
      exits 0.

## Implementation Plan

### Approach

All changes are in `tests/unit/test_migrate_command.py`. No production code
changes (those are in ticket 001).

### Files to Modify

- `tests/unit/test_migrate_command.py`

### New Test Class

Add `TestMergeModeCleansUpSourceDir` after the existing
`TestExecuteMovesPerformsMove` class. Use the existing `_make_project` helper
(already present in the test file) to construct a `Project` with default path
config.

```python
class TestMergeModeCleansUpSourceDir:
    """Regression tests for the merge-mode source-directory cleanup fix."""

    def test_source_dir_removed_when_dest_has_only_gitkeep(self, tmp_path):
        """The exact bug scenario: init pre-creates dest with .gitkeep,
        forcing merge mode; after migration the source dir must be gone."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "idea.md").write_text("# My idea", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()  # simulates what init scaffolds

        moves = detect_moves(project)
        issues_move = next(m for m in moves if m.category == "issues")
        # With fix 1: dest has only .gitkeep so mode should be "move".
        # Even if it is "merge" (safety-net path), the source must still be gone.
        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert (dst_dir / "idea.md").exists(), "Artifact must reach destination"
        assert not src_dir.exists(), "Source dir must be fully removed"

    def test_detect_moves_treats_gitkeep_only_dest_as_move_mode(self, tmp_path):
        """detect_moves returns mode='move' when dest contains only .gitkeep."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "idea.md").write_text("# idea", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / ".gitkeep").touch()

        moves = detect_moves(project)
        issues_move = next(m for m in moves if m.category == "issues")
        assert issues_move.mode == "move", (
            f"Expected mode='move' for gitkeep-only dest; got '{issues_move.mode}'"
        )

    def test_no_clobber_preserved_in_merge_with_real_dst_file(self, tmp_path):
        """A real artifact in dest still triggers merge mode (no-clobber)."""
        src_dir = tmp_path / ".clasi" / "issues"
        src_dir.mkdir(parents=True)
        (src_dir / "conflict.md").write_text("from src", encoding="utf-8")

        project = _make_project(tmp_path)
        dst_dir = project.issues_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / "conflict.md").write_text("original", encoding="utf-8")

        moves = detect_moves(project)
        issues_move = next(m for m in moves if m.category == "issues")
        assert issues_move.mode == "merge", (
            "Real dst artifact must force merge mode"
        )

        with patch("clasi.migrate_command._is_git_repo", return_value=False):
            execute_moves(project, moves)

        assert (dst_dir / "conflict.md").read_text(encoding="utf-8") == "original", (
            "Existing dst file must not be clobbered"
        )
```

### Tighten Existing Assertion

In `TestExecuteMovesPerformsMove.test_file_moved_to_destination`, change:

```python
        assert not src_dir.exists() or not any(src_dir.iterdir())
```

to:

```python
        assert not src_dir.exists()
```

### Testing Plan

```
uv run pytest tests/unit/test_migrate_command.py tests/unit/test_relocate.py -q
```

All tests (existing and new) must pass. The new tests will fail on the
un-patched code (reproducing the bug) and pass after ticket 001 is applied.

### Documentation Updates

No documentation updates required.
