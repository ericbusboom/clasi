---
id: 009
title: 'Remove PHASES feature flag: make schema-derived path unconditional'
status: done
use-cases:
- SUC-001
- SUC-003
depends-on:
- 008
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove PHASES feature flag: make schema-derived path unconditional

## Description

Remove the `CLASI_SCHEMA_PHASES` feature flag and `_PHASES_FALLBACK` constant
from `state_db_class.py`. Make the schema-derived path the only path.

This ticket executes in the same sprint as ticket 008 — immediately after the
flag has been validated by the end-to-end tests in ticket 013. The flag is
not intended to survive more than one release; this ticket removes it in the
same sprint.

The module-level `PHASES` assignment becomes unconditional:

```python
from clasi.schemas import loader as _loader
from clasi.schemas.graph import ArtifactGraph as _ArtifactGraph
import importlib.resources as _res
_schema_path = _res.files("clasi.schemas").joinpath("se-process", "schema.yaml")
PHASES = _ArtifactGraph(_loader.load(_schema_path)).phases()
```

## Acceptance Criteria

- [x] `_PHASES_FALLBACK` constant is removed from `state_db_class.py`.
- [x] The `CLASI_SCHEMA_PHASES` env-var branch is removed.
- [x] `PHASES` is unconditionally derived from `se-process/schema.yaml` at module import.
- [x] All existing tests that reference `PHASES` pass unchanged (the derived value is identical to the old hardcoded value).
- [x] The `CLASI_SCHEMA_PHASES=1` test added in ticket 008 is removed or updated to test the unconditional path.
- [x] `uv run pytest` passes.

## Implementation Plan

**Approach**: Delete the `if/else` block, delete `_PHASES_FALLBACK`, leave
only the unconditional schema-derived assignment. Remove the monkeypatch test
from ticket 008 (or convert it to a test that simply asserts `PHASES` is a
non-empty list derived from a loaded schema).

**Files to modify**:
- `clasi/state_db_class.py` — remove flag + fallback
- `tests/clasi/test_state_db_class.py` — update/remove feature flag test

**Testing plan**: `uv run pytest` passing with all existing tests is the
primary criterion. Optionally add a test asserting `PHASES[0] == "roadmap"`.

**Documentation updates**: None.
