---
id: "012-002"
title: Fix sprint artifact predicates via sprint_artifact_exists protocol method
status: done
use-cases: [SUC-002]
depends-on: ["012-001"]
issue:
- gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md
- gh-18-predicates-read-legacy-docs-clasi-bare-id-paths-while-writers-use.md
---

# 012-002: Fix sprint artifact predicates via sprint_artifact_exists protocol method

## Description

The four sprint artifact predicates (`is_sprint_doc_present`, `is_architecture_present`,
`is_usecases_present`, `is_close_report_present`) all hardcode `docs/clasi/sprints/{sprint_id}/...`
paths with bare IDs. The write side uses `.clasi/sprints/<id>-<slug>/` (slugged).
Additionally, `is_usecases_present` checks `use-cases.md` (hyphenated) while the
writer creates `usecases.md`.

This ticket adds `sprint_artifact_exists(sprint_id, artifact_name) -> bool` to the
`StateReader` protocol (consistent with the `overview_exists()` pattern from ticket 001)
and implements it in `ClasiStateReader` by delegating to `project.get_sprint(sprint_id)`,
which already performs the ID-prefix glob. The predicates are then updated to call
this named method instead of `file_exists()` with a hardcoded path.

## Acceptance Criteria

- [x] `StateReader` protocol has `sprint_artifact_exists(sprint_id: str, artifact_name: str) -> bool`.
- [x] `ClasiStateReader.sprint_artifact_exists()` resolves via `project.get_sprint(sprint_id).path / artifact_name` (uses `get_sprint`'s ID-prefix glob).
- [x] `NullStateReader.sprint_artifact_exists()` returns False.
- [x] `is_sprint_doc_present` calls `ctx.reader.sprint_artifact_exists(ctx.sprint_id, "sprint.md")`.
- [x] `is_architecture_present` calls `ctx.reader.sprint_artifact_exists(ctx.sprint_id, "architecture-update.md")`.
- [x] `is_usecases_present` calls `ctx.reader.sprint_artifact_exists(ctx.sprint_id, "usecases.md")` (no hyphen).
- [x] `is_close_report_present` calls `ctx.reader.sprint_artifact_exists(ctx.sprint_id, "close-report.md")`.
- [x] Module docstring in `predicates/sprint.py` updated: remove `file_exists` from the StateReader methods list; add `sprint_artifact_exists`.
- [x] `pytest tests/unit/test_state_machine/test_predicates.py tests/unit/test_status/test_reader.py` passes.

## Implementation Plan

### Approach

Add the named protocol method (APPROVE WITH CHANGES note from architecture review),
then update the four predicates. The method delegates to `get_sprint()` which already
handles slug resolution.

### Files to Modify

**`clasi/state_machine/context.py`** — two additions:
1. Add to `StateReader` Protocol (after `overview_exists`, ~line 131):
```python
def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
    """Return True iff artifact_name exists in the sprint's root directory.

    Resolves the sprint directory by ID-prefix match (<id>-*) as the
    writers do, not by bare sprint ID.
    """
    ...
```
2. Add to `NullStateReader`:
```python
def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
    return False
```

**`clasi/status/reader.py`** — add method to `ClasiStateReader`:
```python
def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
    """Return True iff artifact_name exists in the sprint directory.

    Source: filesystem. Resolves the sprint dir via project.get_sprint()
    which uses ID-prefix glob (<id>-*), matching the write side exactly.
    Returns False if the sprint is not found or on any error.
    """
    try:
        sprint = self._project.get_sprint(sprint_id)
        return (sprint.path / artifact_name).exists()
    except Exception:
        return False
```
Also add `sprint_artifact_exists | Filesystem` to the data-sources docstring table.

**`clasi/state_machine/predicates/sprint.py`** — update four predicates and module docstring:
```python
"""...
StateReader methods used:
- ``sprint_artifact_exists(sprint_id, artifact_name)`` — resolves sprint dir by ID-prefix glob
- ``sprint_gate(sprint_id, gate)`` — gate result dict or None
...
"""

@predicate("is_sprint_doc_present")
def is_sprint_doc_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint document exists for this sprint."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "sprint.md")


@predicate("is_architecture_present")
def is_architecture_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's architecture-update.md exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "architecture-update.md")


@predicate("is_usecases_present")
def is_usecases_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's use cases artifact exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "usecases.md")


@predicate("is_close_report_present")
def is_close_report_present(ctx: SprintContext) -> bool:
    """Return True iff the sprint's close-report.md exists."""
    return ctx.reader.sprint_artifact_exists(ctx.sprint_id, "close-report.md")
```

### Testing Plan

**`tests/unit/test_state_machine/test_predicates.py`**:
1. Add `reader.sprint_artifact_exists.return_value = False` to `_mock_reader` defaults.
2. Update all four sprint-artifact test classes to use `sprint_artifact_exists=True/False`
   kwargs instead of `file_exists=True/False`:
   - `TestIsSprintDocPresent` → `sprint_artifact_exists=True/False`
   - `TestIsArchitecturePresent` → same
   - `TestIsUsecasesPresent` → same
   - `TestIsCloseReportPresent` → same

**`tests/unit/test_status/test_reader.py`** — add tests:
```python
def test_sprint_artifact_exists_true(self, reader, project, tmp_path):
    # Create a slugged sprint dir with sprint.md
    sprint_dir = project.sprints_dir / "001-my-sprint"
    sprint_dir.mkdir(parents=True)
    fm = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
    (sprint_dir / "sprint.md").write_text(fm)
    assert reader.sprint_artifact_exists("001", "sprint.md") is True

def test_sprint_artifact_exists_false_missing_file(self, reader, project, tmp_path):
    sprint_dir = project.sprints_dir / "001-my-sprint"
    sprint_dir.mkdir(parents=True)
    fm = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
    (sprint_dir / "sprint.md").write_text(fm)
    assert reader.sprint_artifact_exists("001", "architecture-update.md") is False

def test_sprint_artifact_exists_false_no_sprint(self, reader):
    assert reader.sprint_artifact_exists("999", "sprint.md") is False
```

### Documentation Updates

Module docstring update in `predicates/sprint.py` as described above.
