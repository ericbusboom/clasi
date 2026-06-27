---
id: '001'
title: Configurable path layer in Project
status: done
use-cases:
- SUC-001
- SUC-003
depends-on: []
github-issue: ''
issue: reorganize-clasi-files-visible-clasi-artifacts-docs-documents-src-code-configurable-self-migrating.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Configurable path layer in Project

## Description

Add a configurable path resolution layer to `clasi/project.py` so every
artifact category resolves from a central defaults table that can be overridden
via `.clasi/config.yaml`. This is the foundational change all other tickets
depend on.

Before this ticket, every category property in `Project` hardcodes a `.clasi/`
prefix (e.g. `self.clasi_dir / "issues"`). After this ticket, each property
delegates to `_resolve_dir(key)` which reads the user's `paths:` config and
falls back to `ARTIFACT_PATH_DEFAULTS`.

Also adds the `reflections_dir` property (previously absent) and the `db_path`
property (previously the DB path was inline in the `db` property). The `db`
property is updated to use `db_path`.

Before implementing, grep `clasi/` for any direct `clasi_dir / "reflections"`
usage outside of `init_command.py` to find callsites that need updating in
ticket 002.

## Acceptance Criteria

- [x] `ARTIFACT_PATH_DEFAULTS` dict is defined at module level in
      `clasi/project.py` with keys: `issues`, `sprints`, `reflections`,
      `architecture`, `design`, `logs`, `db`. Values are: `clasi/issues`,
      `clasi/sprints`, `clasi/reflections`, `docs/architecture`, `docs/design`,
      `.clasi/log`, `.clasi/.clasi.db`.
- [x] `_load_paths_config(root: Path) -> dict` is a module-level function that
      reads `root/.clasi/config.yaml`, returns `data["paths"]` when it is a
      `dict[str, str]`, returns `{}` on `FileNotFoundError`, `YAMLError`, or
      wrong type. Never raises.
- [x] `Project.__init__` initialises `self._paths: dict | None = None`.
- [x] `Project._path_config()` lazily calls `_load_paths_config` on first call
      and caches the result as `self._paths`.
- [x] `Project._resolve_dir(key: str) -> Path` returns
      `self._root / (self._path_config().get(key) or ARTIFACT_PATH_DEFAULTS[key])`.
- [x] `issues_dir`, `sprints_dir`, `architecture_dir`, `design_dir`, `log_dir`
      all delegate to `_resolve_dir`.
- [x] `reflections_dir` is a new property delegating to `_resolve_dir("reflections")`.
- [x] `db_path` is a new property delegating to `_resolve_dir("db")` (returns a
      `Path` to the SQLite file).
- [x] `db` property uses `self.db_path` instead of `self.clasi_dir / ".clasi.db"`.
- [x] `clasi_dir` is unchanged (still `.clasi/`).
- [x] With no `paths:` key, each property returns the new default.
- [x] With a `paths:` override, the override is returned.
- [x] Malformed `paths:` (non-dict, bad YAML) falls back to defaults silently.

## Implementation Plan

### Files to Modify

- `clasi/project.py` — add `ARTIFACT_PATH_DEFAULTS`, `_load_paths_config`;
  update `Project.__init__`; add `_path_config`, `_resolve_dir`, `db_path`,
  `reflections_dir`; rewrite category properties; update `db`.

### Files to Create

- `tests/unit/test_project_paths.py`

### Implementation Steps

1. Add `ARTIFACT_PATH_DEFAULTS` dict at module level in `clasi/project.py`
   after imports (before the class definition).

2. Add `_load_paths_config(root: Path) -> dict` module-level function that
   reads `.clasi/config.yaml`, extracts `paths`, validates it is a
   `dict[str, str]`, and swallows all exceptions into `{}`.

3. In `Project.__init__`, add `self._paths: dict | None = None` after `self._db`.

4. Add `_path_config(self) -> dict` and `_resolve_dir(self, key: str) -> Path`
   as private instance methods.

5. Rewrite `issues_dir`, `sprints_dir`, `architecture_dir`, `design_dir`,
   `log_dir` to call `_resolve_dir` with the appropriate key.

6. Add `reflections_dir` property (key `"reflections"`).

7. Add `db_path` property (key `"db"`).

8. Update `db` property body:
   `self._db = StateDB(self.db_path)`.

9. Grep `clasi/` for `clasi_dir / "reflections"` and `clasi_dir / "log"` to
   identify any callsites missed — record them as comments in the commit for
   ticket 002 to pick up.

### Testing Plan

New file `tests/unit/test_project_paths.py`:

- `test_default_paths_no_config` — `Project(tmp_path).issues_dir` equals
  `tmp_path / "clasi/issues"` when no config.yaml.
- `test_default_paths_empty_paths_key` — same when config.yaml has `process: se`
  but no `paths:` key.
- `test_override_issues` — config.yaml with `paths: {issues: myteam/issues}`;
  `issues_dir` returns override, `sprints_dir` returns default.
- `test_malformed_yaml` — corrupt config.yaml; properties return defaults.
- `test_wrong_type_paths` — `paths: "string"` falls back silently.
- `test_reflections_dir_default` — returns `tmp_path / "clasi/reflections"`.
- `test_db_path_default` — returns `tmp_path / ".clasi/.clasi.db"`.
- `test_lazy_cache` — monkeypatch `_load_paths_config` to count calls; calling
  `issues_dir` twice calls config loader once.
- `test_design_dir_preserved` — `design_dir` returns `tmp_path / "docs/design"`.

Run: `uv run pytest tests/unit/test_project_paths.py -v`
