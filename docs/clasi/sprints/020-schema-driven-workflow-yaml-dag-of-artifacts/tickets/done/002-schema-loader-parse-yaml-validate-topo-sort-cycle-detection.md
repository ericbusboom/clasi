---
id: "002"
title: "Schema loader: parse YAML, validate, topo-sort, cycle detection"
status: done
use-cases: [SUC-001, SUC-002]
depends-on: ["001"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Schema loader: parse YAML, validate, topo-sort, cycle detection

## Description

Implement `clasi/schemas/loader.py`: the `load(path) -> WorkflowSchema`
function that parses a YAML schema file, validates it with Pydantic, and runs
structural checks (duplicate IDs, missing `requires` references, cycles,
unknown gate kinds).

This is the only path that reads schema YAML files. No other module parses
YAML directly.

The loader is a pure function — no side effects, no imports from other `clasi`
modules. It depends only on stdlib, PyYAML, and Pydantic.

## Acceptance Criteria

- [x] `loader.load(path: str | Path) -> WorkflowSchema` parses the YAML at `path` using PyYAML `safe_load`.
- [x] Pydantic validation runs on the parsed dict; unknown fields raise `SchemaError` wrapping the Pydantic error.
- [x] Duplicate `id` values across `artifacts` raise `SchemaError` naming the duplicated ID.
- [x] Any `requires` entry that references an unknown artifact `id` raises `SchemaError` naming the missing ID.
- [x] A cycle in the `requires` graph raises `SchemaError` identifying the cycle (Kahn's algorithm or DFS).
- [x] Any `gate.kind` not in the registry `{"stakeholder-review", "review", "per-ticket"}` raises `SchemaError` naming the unknown kind.
- [x] A valid schema returns a `WorkflowSchema` instance with `artifacts` in topological order.
- [x] `loader.py` has zero imports from `clasi.*` (only stdlib, pyyaml, pydantic, and the models from `clasi.schemas`).
- [x] `uv run pytest` passes.

## Implementation Plan

**Approach**: Implement Kahn's algorithm for topological sort. The gate-kind
registry is a module-level frozenset constant in `loader.py`. All validation
raises `SchemaError` with a descriptive message. The sorted artifact list
replaces the original list in the returned `WorkflowSchema`.

**Files to modify**:
- `clasi/schemas/loader.py` — replace stub with full implementation

**Testing plan**: Unit tests come in ticket 004. After implementing, manually
verify that `loader.load("clasi/schemas/se-process/schema.yaml")` works once
the schema file exists (ticket 005). In this ticket, write a minimal inline
smoke test or use the REPL to verify the happy path with a small hand-crafted
schema dict.

**Documentation updates**: None.
