---
id: "016-001"
title: "Delta model: Pydantic types for ADDED/MODIFIED/REMOVED/RENAMED items"
status: todo
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
depends-on: []
issue: delta-specs-for-brownfield-architecture-changes.md
---

# 016-001: Delta model — Pydantic types for delta items

## Description

Create the `clasi/delta/` package and define the Pydantic types that the
parser will work with. This ticket is the foundation; all other delta
tickets depend on it.

No merger types are included — the delta format does not produce a merge
step. `DeltaMergeError` is not part of this sprint.

## Acceptance Criteria

- [ ] `clasi/delta/__init__.py` exists (can be empty).
- [ ] `clasi/delta/model.py` defines:
  - `DeltaItem(name: str, kind: Literal["ADDED","MODIFIED","REMOVED","RENAMED"], category: Literal["Components","Scenarios"], body: str, new_name: str | None = None)`
  - `ArchitectureDelta(items: list[DeltaItem])`
  - `DeltaParseError(Exception)` with fields `line: int`, `message: str`, `rule: str`
- [ ] All types are importable from `clasi.delta.model`.
- [ ] `tests/unit/delta/__init__.py` exists.
- [ ] `tests/unit/delta/test_model.py` exists with basic instantiation tests for all types.
- [ ] All tests pass.

## Implementation Plan

### Approach

Create a new `clasi/delta/` package. Define Pydantic models for the delta
format. This is purely additive — no existing code is modified.

### Files to Create

- `clasi/delta/__init__.py`
- `clasi/delta/model.py`
- `tests/unit/delta/__init__.py`
- `tests/unit/delta/test_model.py`

### Testing Plan

- Test `DeltaItem` instantiation with each valid `kind` and `category`.
- Test that invalid `kind` or `category` values are rejected by Pydantic.
- Test `ArchitectureDelta` with an empty item list and a populated list.
- Test `DeltaParseError` can be raised and caught with the correct fields.

### Documentation Updates

None for this ticket — the architecture-update.md for this sprint documents
the module.
