---
id: '003'
title: Update init to use path table and write paths block
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update init to use path table and write paths block

## Description

Replace the hardcoded directory scaffold in `clasi/init_command.py` with
iteration over `ARTIFACT_PATH_DEFAULTS` (imported from `clasi/project.py`).
Also write the `paths:` block to `.clasi/config.yaml` on every `init` run,
using `setdefault` to avoid overwriting a user's custom values.

Current code (lines ~199–239 of `init_command.py`):
- Creates `clasi_dir / "issues"` explicitly.
- Loops over `("sprints", "architecture", "reflections")` hardcoded tuple.
- Creates `clasi_dir / "log"` explicitly.

After this ticket:
- Iterates `ARTIFACT_PATH_DEFAULTS.items()`, resolves
  `target_path / rel` for each non-`db` key.
- Preserves special cases: `logs` key gets the `.gitignore`; all other
  directory keys get a `.gitkeep` if empty.
- After writing `process:` to config.yaml, also writes the `paths:` block
  via `config_data.setdefault("paths", dict(ARTIFACT_PATH_DEFAULTS))`.

## Acceptance Criteria

- [x] `init_command.py` no longer contains hardcoded `"issues"`, `"sprints"`,
      `"architecture"`, `"reflections"` directory names in the scaffold section.
- [x] `ARTIFACT_PATH_DEFAULTS` is imported from `clasi.project` and used for
      directory creation.
- [x] `clasi init` in a scratch dir creates `clasi/issues/`, `clasi/sprints/`,
      `clasi/reflections/`, `docs/architecture/`, `docs/design/`, `.clasi/log/`.
- [x] Each directory gets a `.gitkeep` (when empty); `log/` gets a `.gitignore`.
- [x] `paths:` block is written to `.clasi/config.yaml`.
- [x] Re-running `clasi init` on a project with a custom `paths:` key does NOT
      overwrite the custom values (setdefault semantics).
- [x] `uv run pytest` passes.

## Implementation Plan

### Files to Modify

- `clasi/init_command.py` — lines ~199–239 (scaffold section + config write).

### Implementation Steps

1. Add `from clasi.project import ARTIFACT_PATH_DEFAULTS` to imports in
   `init_command.py`.

2. Replace the hardcoded scaffold section with a loop:
   ```python
   for key, rel in ARTIFACT_PATH_DEFAULTS.items():
       if key == "db":
           continue  # db is a file; created by StateDB on first use
       dir_path = target_path / rel
       dir_path.mkdir(parents=True, exist_ok=True)
       if key == "logs":
           gitignore = dir_path / ".gitignore"
           gitignore.write_text("# Ignore all log files\n*\n!.gitignore\n", encoding="utf-8")
       else:
           gk = dir_path / ".gitkeep"
           if not gk.exists() and not any(dir_path.iterdir()):
               gk.touch()
   ```

3. After setting `config_data["process"] = process`, add:
   ```python
   config_data.setdefault("paths", dict(ARTIFACT_PATH_DEFAULTS))
   ```

4. Update the click.echo messages to reflect the new directory names.

### Testing Plan

Update `tests/unit/test_init_command.py` (or the integration test file) to:
- Assert `clasi/issues/` is created in the scratch dir.
- Assert `docs/architecture/` is created.
- Assert `paths:` block exists in `.clasi/config.yaml` after init.
- Assert re-running init with an existing custom `paths.issues` value leaves
  it unchanged.

Run: `uv run pytest tests/ -x -v`
