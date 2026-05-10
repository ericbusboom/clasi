---
id: "008"
title: "state_db_class.py: derive PHASES from schema behind feature flag"
status: done
use-cases: [SUC-001, SUC-003]
depends-on: ["003", "005"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# state_db_class.py: derive PHASES from schema behind feature flag

## Description

Modify `clasi/state_db_class.py` to derive the `PHASES` list from the active
schema when the `CLASI_SCHEMA_PHASES=1` environment variable is set. The
existing hardcoded list moves to `_PHASES_FALLBACK` and is used when the flag
is absent or `"0"`.

The schema-derived path: load the se-process schema using `loader.load()`,
wrap it in `ArtifactGraph`, call `graph.phases()`, assign to `PHASES`. This
happens at module import time so all callers see the correct list.

The derived list must equal `_PHASES_FALLBACK` for a correct se-process
schema. A startup assertion can enforce this during the transition.

## Acceptance Criteria

- [x] `PHASES` remains a module-level list named `PHASES` (no callers are changed).
- [x] The existing list is renamed to `_PHASES_FALLBACK` and kept at module level.
- [x] When `CLASI_SCHEMA_PHASES` env var is `"1"`, `PHASES` is derived by loading `se-process/schema.yaml` via `ArtifactGraph.phases()`.
- [x] When `CLASI_SCHEMA_PHASES` env var is absent or any other value, `PHASES = _PHASES_FALLBACK` (unchanged behavior).
- [x] A startup check asserts that the schema-derived list equals `_PHASES_FALLBACK` when the flag is active; logs a WARNING and falls back if they differ.
- [x] The schema path used is resolved relative to the `clasi/schemas/` package directory (using `importlib.resources` or `Path(__file__).parent`).
- [x] All existing `state_db_class.py` tests pass unchanged.
- [x] New test: `CLASI_SCHEMA_PHASES=1` yields a `PHASES` list identical to `_PHASES_FALLBACK`.
- [x] `uv run pytest` passes.

## Implementation Plan

**Approach**: At module level in `state_db_class.py`, after defining
`_PHASES_FALLBACK`, add:

```python
import os as _os
if _os.environ.get("CLASI_SCHEMA_PHASES") == "1":
    from clasi.schemas import loader as _loader
    from clasi.schemas.graph import ArtifactGraph as _ArtifactGraph
    import importlib.resources as _res
    _schema_path = _res.files("clasi.schemas.se-process").joinpath("schema.yaml")
    _schema = _loader.load(_schema_path)
    PHASES = _ArtifactGraph(_schema).phases()
    if PHASES != _PHASES_FALLBACK:
        import warnings
        warnings.warn(f"Schema-derived PHASES differs from fallback; using fallback", stacklevel=1)
        PHASES = _PHASES_FALLBACK
else:
    PHASES = _PHASES_FALLBACK
```

**Files to modify**:
- `clasi/state_db_class.py`
- `tests/clasi/test_state_db_class.py` — add test for `CLASI_SCHEMA_PHASES=1` path

**Testing plan**: Use `monkeypatch.setenv("CLASI_SCHEMA_PHASES", "1")` in the
test. Force module reimport with `importlib.reload` or by testing the derived
list directly via the graph.

**Documentation updates**: None in this ticket (feature flag documented in architecture-update.md).
