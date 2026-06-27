---
id: "012-001"
title: Fix Project.design_dir and add overview_exists to StateReader protocol
status: done
use-cases: [SUC-001, SUC-004]
depends-on: []
issue:
- fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md
- gh-17-initialize-gate-checks-docs-clasi-overview-md-but-skill-writes-clasi.md
---

# 012-001: Fix Project.design_dir and add overview_exists to StateReader protocol

## Description

NOTE: The implementation was reconciled per the critical override in sprint instructions.
`Project.design_dir` was LEFT UNCHANGED (returns `docs/design/`). The fix is purely
in the predicate/reader layer: `overview_exists()` was added to the `StateReader`
protocol and `ClasiStateReader`, deriving the path from `self._project.design_dir`
(which resolves to `docs/design/overview.md`). The overview predicates now call
`ctx.reader.overview_exists()` instead of hardcoding a stale path.

## Acceptance Criteria

- [x] `Project.design_dir` remains `self._root / "docs" / "design"` (unchanged — design docs stay in docs/design/).
- [x] `StateReader` protocol has `overview_exists(self) -> bool` method.
- [x] `ClasiStateReader.overview_exists()` returns True iff `project.design_dir / "overview.md"` exists (resolves to `docs/design/overview.md`).
- [x] `NullStateReader.overview_exists()` returns False (safe default).
- [x] `is_overview_present(ctx)` calls `ctx.reader.overview_exists()` (not `file_exists`).
- [x] `is_overview_absent(ctx)` calls `not ctx.reader.overview_exists()`.
- [x] Stale docstring in `predicates/project.py` module header updated (reference to `docs/clasi/overview.md` removed).
- [x] `pytest tests/unit/test_project.py tests/unit/test_state_machine/test_predicates.py tests/unit/test_status/test_reader.py` passes.

## Implementation Plan

### Approach

Three files change; changes are small and non-breaking within each file.

### Files to Modify

**`clasi/project.py`** — change `design_dir` property (lines 47-49):
```python
@property
def design_dir(self) -> Path:
    """.clasi/design/ — overview, specification, usecases."""
    return self.clasi_dir / "design"
```

**`clasi/state_machine/context.py`** — two additions:
1. Add to `StateReader` Protocol (after `ticket_count` method, ~line 129):
```python
def overview_exists(self) -> bool:
    """Return True iff the project overview exists at the canonical design path."""
    ...
```
2. Add to `NullStateReader` (after `ticket_count` method, ~line 214):
```python
def overview_exists(self) -> bool:
    return False
```

**`clasi/status/reader.py`** — add method to `ClasiStateReader` (after `file_exists`, ~line 82):
```python
def overview_exists(self) -> bool:
    """Return True iff .clasi/design/overview.md exists.

    Source: filesystem. Derives path from project.design_dir so that
    changing design_dir propagates automatically.
    """
    try:
        return (self._project.design_dir / "overview.md").exists()
    except Exception:
        return False
```
Also update the data-sources table in the module docstring to add `overview_exists | Filesystem`.

**`clasi/state_machine/predicates/project.py`** — update two predicates and docstring:
```python
"""...
StateReader methods used:
- ``overview_exists()`` — checks for .clasi/design/overview.md
- ...
"""

@predicate("is_overview_absent")
def is_overview_absent(ctx: ProjectContext) -> bool:
    """Return True iff the project overview is absent."""
    return not ctx.reader.overview_exists()


@predicate("is_overview_present")
def is_overview_present(ctx: ProjectContext) -> bool:
    """Return True iff the project overview exists."""
    return ctx.reader.overview_exists()
```

### Testing Plan

**`tests/unit/test_project.py`** — update the `design_dir` assertion (line ~30) to:
```python
assert project.design_dir == tmp_path / ".clasi" / "design"
```

**`tests/unit/test_state_machine/test_predicates.py`** — two changes:
1. Add `reader.overview_exists.return_value = False` to `_mock_reader` defaults (~line 109).
2. Update `TestIsOverviewAbsent` and `TestIsOverviewPresent` to use `overview_exists=True/False` kwargs instead of `file_exists=True/False`:
```python
class TestIsOverviewAbsent:
    def test_true_when_overview_missing(self):
        reader = _mock_reader(overview_exists=False)
        ...
    def test_false_when_overview_present(self):
        reader = _mock_reader(overview_exists=True)
        ...
```

**`tests/unit/test_status/test_reader.py`** — add two test methods to the reader test class:
```python
def test_overview_exists_true(self, reader, project):
    design_dir = project.design_dir
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "overview.md").write_text("# Overview")
    assert reader.overview_exists() is True

def test_overview_exists_false(self, reader, project):
    # design dir doesn't exist by default in fixture
    assert reader.overview_exists() is False
```

### Documentation Updates

None beyond inline docstring fixes in the modified files.
