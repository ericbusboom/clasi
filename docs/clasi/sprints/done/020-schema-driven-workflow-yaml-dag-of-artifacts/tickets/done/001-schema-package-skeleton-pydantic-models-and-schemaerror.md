---
id: '001'
title: 'Schema package skeleton: Pydantic models and SchemaError'
status: done
use-cases: [SUC-001, SUC-002]
depends-on: []
github-issue: ''
todo: schema-driven-workflow-yaml-dag.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Schema package skeleton: Pydantic models and SchemaError

## Description

Create the `clasi/schemas/` package with its public interface, Pydantic data
models, and the `SchemaError` exception. This is the foundation that all other
tickets in this sprint depend on. No YAML parsing yet — just the type
definitions and package surface.

The package defines three Pydantic models: `GateSpec`, `ArtifactSpec`, and
`WorkflowSchema`. It also defines `SchemaError` and re-exports the key symbols
from `__init__.py`.

`clasi/schemas/__init__.py` must export: `SchemaError`, `GateSpec`,
`ArtifactSpec`, `WorkflowSchema`. The `loader.py` and `graph.py` modules are
stubs in this ticket — they get filled in by tickets 002 and 003.

## Acceptance Criteria

- [x] `clasi/schemas/__init__.py` exists and exports `SchemaError`, `GateSpec`, `ArtifactSpec`, `WorkflowSchema`.
- [x] `clasi/schemas/loader.py` exists as a stub (`load()` raises `NotImplementedError`).
- [x] `clasi/schemas/graph.py` exists as a stub (`class ArtifactGraph: pass`).
- [x] `GateSpec` Pydantic model: required fields `kind: str`, `record: str`.
- [x] `ArtifactSpec` Pydantic model: required `id: str`, `generates: str`; optional `instruction: str | None`, `requires: list[str]` (default `[]`), `gate: GateSpec | None`, `lock: str | None`.
- [x] `WorkflowSchema` Pydantic model: required `version: int`, `name: str`, `description: str`, `artifacts: list[ArtifactSpec]`.
- [x] `SchemaError` is a subclass of `Exception`.
- [x] All three models use `model_config = ConfigDict(extra="forbid")` to reject unknown fields.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

**Approach**: Create the package directory and three Python files. Use Pydantic
v2 (`from pydantic import BaseModel, ConfigDict`). No PyYAML import in this
ticket.

**Files to create**:
- `clasi/schemas/__init__.py` — re-export `SchemaError`, `GateSpec`, `ArtifactSpec`, `WorkflowSchema`
- `clasi/schemas/loader.py` — stub: `def load(path): raise NotImplementedError("loader not yet implemented")`
- `clasi/schemas/graph.py` — stub: `class ArtifactGraph: pass`

**Files to modify**:
- `pyproject.toml` — confirm `pyyaml` is in dependencies (add if absent); `pydantic` should already be present

**Testing plan**: No new tests required in this ticket (tests come in ticket
004). After creating the files, verify that `from clasi.schemas import
SchemaError, GateSpec, ArtifactSpec, WorkflowSchema` works in a Python shell
and that `uv run pytest` passes.

**Documentation updates**: None in this ticket.
