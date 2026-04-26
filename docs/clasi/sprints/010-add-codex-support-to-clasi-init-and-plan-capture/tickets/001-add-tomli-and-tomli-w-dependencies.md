---
id: "001"
title: "Add tomli and tomli-w dependencies"
status: done
use-cases:
  - SUC-012
depends-on: []
github-issue: ""
todo: "add-codex-support-to-clasi-init-and-plan-capture.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add tomli and tomli-w dependencies

## Description

Python 3.11 introduced `tomllib` as a stdlib module for reading TOML files, but it is
read-only and unavailable on Python 3.10. The Codex installer (ticket 004) needs to
read and write `.codex/config.toml`. This ticket adds the two required dependencies to
`pyproject.toml` and verifies they can be imported and round-tripped correctly.

This ticket has no behavior code. It is pure dependency addition and import verification.
All code that uses TOML is in ticket 004.

## Acceptance Criteria

- [x] `pyproject.toml` includes `tomli-w>=1.0` as an unconditional runtime dependency.
- [x] `pyproject.toml` includes `tomli>=2.0; python_version < "3.11"` as a conditional
      runtime dependency.
- [x] `uv sync` (or `pip install -e .`) resolves without errors.
- [x] A new test `tests/unit/test_toml_compat.py` verifies:
  - The TOML import shim (`try: import tomllib except ImportError: import tomli as tomllib`)
    imports without error.
  - A small dict written with `tomli_w.dumps()` and read back with `tomllib.loads()`
    round-trips correctly.

## Implementation Plan

### Files to modify

- `pyproject.toml` — add two entries to `[project.dependencies]`.
- `uv.lock` — regenerated automatically by `uv sync`.

### Files to create

- `tests/unit/test_toml_compat.py`

### Approach

1. Add to `[project.dependencies]` in `pyproject.toml`:
   ```
   "tomli-w>=1.0",
   "tomli>=2.0; python_version < '3.11'",
   ```
2. Run `uv sync` to update the lock file.
3. Write `tests/unit/test_toml_compat.py` with two test functions:
   - `test_toml_shim_importable`: exercises the conditional import shim.
   - `test_toml_round_trip`: writes `{"section": {"key": "value"}}` with `tomli_w`,
     reads it back with `tomllib`, asserts equality.

### Testing plan

```
uv run pytest tests/unit/test_toml_compat.py -v
uv run pytest -x
```

### Documentation updates

None.
