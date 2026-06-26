---
id: "012-001"
title: Fix Project.design_dir and add overview_exists to StateReader protocol
status: open
use-cases: [SUC-001, SUC-004]
depends-on: []
issue:
- fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md
- gh-17-initialize-gate-checks-docs-clasi-overview-md-but-skill-writes-clasi.md
---

# 012-001: Fix Project.design_dir and add overview_exists to StateReader protocol

## Description

The `Project.design_dir` property currently returns `docs/design/`, which does not
match the canonical `.clasi/design/` location used by the project-initiation skill,
sprint-planner, and all documented conventions. This causes `is_overview_present`
to check the wrong path, permanently blocking the `uninitialized → planning` transition.

This ticket fixes the root cause: `Project.design_dir` → `.clasi/design/`, adds
`overview_exists()` to the `StateReader` protocol and `ClasiStateReader`, and
updates the overview predicates to call `ctx.reader.overview_exists()` instead of
`ctx.reader.file_exists("docs/clasi/overview.md")`.

This ticket is the foundation for all other tickets in this sprint — it establishes
the correct design dir path that sprint/ticket path fixes build on.

## Acceptance Criteria

- [ ] `Project.design_dir` returns `self.clasi_dir / "design"` (`.clasi/design/`).
- [ ] `StateReader` protocol has `overview_exists(self) -> bool` method.
- [ ] `ClasiStateReader.overview_exists()` returns True iff `.clasi/design/overview.md` exists, deriving the path from `self._project.design_dir`.
- [ ] `NullStateReader.overview_exists()` returns False (safe default).
- [ ] `is_overview_present(ctx)` calls `ctx.reader.overview_exists()` (not `file_exists`).
- [ ] `is_overview_absent(ctx)` calls `not ctx.reader.overview_exists()`.
- [ ] Stale docstring in `predicates/project.py` module header removed (reference to `docs/clasi/overview.md`).
- [ ] `pytest tests/unit/test_project.py tests/unit/test_state_machine/test_predicates.py tests/unit/test_status/test_reader.py` passes.

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
