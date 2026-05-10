---
id: "004"
title: "Loader unit tests: every rejection branch"
status: todo
use-cases: [SUC-002]
depends-on: ["002"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Loader unit tests: every rejection branch

## Description

Write unit tests for `loader.load()` covering every path that raises
`SchemaError`. The TODO states "loader owes existing tests for cycle detection
and missing-dependency errors before any production code reads from it." This
ticket fulfills that requirement.

Tests use in-memory YAML strings (via `tempfile` or `io.StringIO` +
`loader.load_from_dict()` helper) so no fixture files are needed. Cover every
rejection branch documented in the loader.

## Acceptance Criteria

- [ ] Test: valid minimal schema (two artifacts, one `requires`) loads successfully.
- [ ] Test: duplicate artifact `id` raises `SchemaError` with the duplicate ID in the message.
- [ ] Test: `requires` referencing a non-existent ID raises `SchemaError` naming the missing ID.
- [ ] Test: cycle `A -> B -> A` raises `SchemaError`.
- [ ] Test: three-node cycle `A -> B -> C -> A` raises `SchemaError`.
- [ ] Test: unknown `gate.kind` raises `SchemaError` naming the unknown kind.
- [ ] Test: extra unknown field on artifact (e.g., `foo: bar`) raises `SchemaError` (Pydantic `extra="forbid"`).
- [ ] Test: missing required field `id` on artifact raises `SchemaError`.
- [ ] Test: artifact with no `requires` field defaults to empty list (not a rejection).
- [ ] All tests live in `tests/clasi/schemas/test_loader.py`.
- [ ] `uv run pytest tests/clasi/schemas/` passes.

## Implementation Plan

**Approach**: Write YAML strings inline as test fixtures (using Python triple-quoted
strings passed to `tempfile.NamedTemporaryFile` or a `load_from_dict` helper that
accepts an already-parsed dict, bypassing file I/O for speed). If adding
`load_from_dict(d: dict) -> WorkflowSchema` to `loader.py` makes tests cleaner,
add it; it is a thin wrapper that skips YAML parsing and runs straight to
validation.

**Files to create**:
- `tests/clasi/schemas/__init__.py` (empty)
- `tests/clasi/schemas/test_loader.py`

**Files to modify**:
- `clasi/schemas/loader.py` — optionally add `load_from_dict(d: dict) -> WorkflowSchema` helper

**Testing plan**: This ticket IS the tests. Run `uv run pytest tests/clasi/schemas/test_loader.py -v` to verify all branches are covered.

**Documentation updates**: None.
