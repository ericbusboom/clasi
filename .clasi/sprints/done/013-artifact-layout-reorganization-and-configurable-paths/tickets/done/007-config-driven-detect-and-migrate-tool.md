---
id: '007'
title: Config-driven detect-and-migrate tool
status: done
use-cases:
- SUC-004
depends-on:
- '001'
- '002'
- '003'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Config-driven detect-and-migrate tool

## Description

Generalize `clasi/migrate_command.py` from a one-shot `docs/clasi/ → .clasi/`
move into a config-driven detect-and-move tool. The new design:

1. A static `CANDIDATE_LOCATIONS` table lists legacy/alternate source paths per
   category (where files might be today before migration).
2. `detect_moves(project) -> list[Move]` — pure function; probes candidates,
   emits a `Move` for each category whose source exists and differs from the
   current configured destination. Returns empty list if nothing to do.
3. `execute_moves(project, moves, dry_run=False)` — impure; calls
   `_git_mv`/`shutil.move`, rewrites `.gitignore`, cleans empty parents,
   resets `project._db = None` if db moved. Never clobbers existing dest files.
4. `run_migrate` becomes a thin wrapper over detect/execute + `run_init`
   refresh + restart notice. Removes the hard `dst.exists()` guard (that
   guard exists in the current code; the new code must handle this gracefully).

This ticket builds the core logic (steps 1–4) and updates the existing unit
tests. Ticket 008 wires the prompt into `clasi init`.

Do NOT run this against this repo's actual files during implementation. Test
only against scratch `tmp_path` directories.

## Acceptance Criteria

- [x] `Move` dataclass (or NamedTuple) with fields: `category: str`,
      `src: Path`, `dst: Path`, `mode: str` (`"move"` or `"merge"`),
      `is_file: bool`.
- [x] `CANDIDATE_LOCATIONS: dict[str, list[str]]` is module-level in
      `migrate_command.py`. Keys: all `ARTIFACT_PATH_DEFAULTS` keys.
      Each value is a list of root-relative paths to probe in order:
      - `issues`: `[".clasi/issues", "docs/clasi/issues"]`
      - `sprints`: `[".clasi/sprints", "docs/clasi/sprints"]`
      - `reflections`: `[".clasi/reflections", "docs/clasi/reflections"]`
      - `architecture`: `[".clasi/architecture", "docs/clasi/architecture"]`
      - `design`: `[".clasi/design", "docs/clasi/design"]`
      - `logs`: `[".clasi/log", "docs/clasi/log"]`
      - `db`: `[".clasi/.clasi.db", "docs/clasi/.clasi.db"]`
- [x] `detect_moves(project) -> list[Move]`:
      - For each category, resolves destination from `project`.
      - Probes `CANDIDATE_LOCATIONS[category]` in order; uses the first
        existing path as `src`.
      - Skips if `src == dst` (already in place).
      - Skips if `src` does not exist or is empty (for directories).
      - Sets `mode="merge"` if `dst` already exists and is non-empty;
        `mode="move"` otherwise.
      - Sets `is_file=True` for `db` category.
      - Returns `[]` if nothing to do.
- [x] `execute_moves(project, moves, dry_run=False)`:
      - For each `Move`, ensures `dst.parent` exists before moving.
      - Uses `git mv` if in a git repo, else `shutil.move`.
      - For `mode="merge"`: skips individual files that already exist at dst
        (warn, don't clobber); moves non-conflicting files only.
      - Updates `.gitignore`: replaces each `src`-based log path with
        `dst`-based path (generalizes the existing single replace).
      - Cleans up empty parent dirs after each move.
      - Resets `project._db = None` when the `db` category is moved.
      - Dry-run mode prints proposed actions without performing them.
      - Checks no execution lock is held before any moves (scan all candidate
        db locations + configured db_path).
- [x] `run_migrate` is rewritten as: `detect_moves → if empty, report nothing
      to do; else execute_moves(dry_run=False) → run_init → restart notice`.
- [x] The old `if dst.exists(): raise SystemExit(1)` guard is removed from
      `run_migrate`.
- [x] `tests/unit/test_migrate_command.py` is updated: remove tests that
      assert the old `dst.exists()` guard exits; add tests for the new flow.
- [x] `uv run pytest tests/unit/test_migrate_command.py` passes.

## Implementation Plan

### Files to Modify

- `clasi/migrate_command.py` — full rewrite of public interface; keep helpers
  `_is_git_repo`, `_git_mv` as-is; generalize `_update_gitignore` and
  `_check_no_execution_lock`.

### Files to Create

None in this ticket (test file updates only; `test_relocate.py` is in ticket 008).

### Implementation Steps

1. Add `Move` dataclass at module level.

2. Add `CANDIDATE_LOCATIONS` dict.

3. Implement `detect_moves(project) -> list[Move]`.

4. Generalize `_update_gitignore` to accept a list of `(old_str, new_str)` pairs.

5. Generalize `_check_no_execution_lock` to accept a list of db paths to probe.

6. Implement `execute_moves(project, moves, dry_run=False)`.

7. Rewrite `run_migrate` as a thin wrapper.

8. Update `tests/unit/test_migrate_command.py` to match the new interface.

### Testing Plan

In `tests/unit/test_migrate_command.py`:
- `test_detect_moves_nothing_to_do(tmp_path)` — empty project with no
  legacy files; `detect_moves` returns `[]`.
- `test_detect_moves_finds_clasi_issues(tmp_path)` — seed `tmp_path/.clasi/issues/`
  with a file; configure project to use `clasi/issues` as destination;
  assert `detect_moves` returns one `Move(category="issues", ...)`.
- `test_detect_moves_skips_when_src_eq_dst(tmp_path)` — seed files where src
  already equals dst; assert empty list.
- `test_execute_moves_performs_move(tmp_path)` — seed legacy location, call
  `execute_moves`; assert file now at destination, src gone.
- `test_execute_moves_idempotent(tmp_path)` — run twice; second `detect_moves`
  returns `[]`.
- `test_execute_moves_dry_run(tmp_path)` — dry_run=True; file unchanged.
- `test_run_migrate_nothing_to_do(tmp_path)` — no legacy files; run_migrate
  completes without error.
- `test_legacy_docs_clasi_still_works(tmp_path)` — seed `docs/clasi/` layout;
  run_migrate moves files; verify at new locations.

Run: `uv run pytest tests/unit/test_migrate_command.py -v`
