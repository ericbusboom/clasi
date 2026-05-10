---
id: "003"
title: "ArtifactGraph: phases, artifact, requires, gate_for queries"
status: todo
use-cases: [SUC-001, SUC-003]
depends-on: ["002"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# ArtifactGraph: phases, artifact, requires, gate_for queries

## Description

Implement `clasi/schemas/graph.py`: the `ArtifactGraph` class that wraps a
loaded `WorkflowSchema` and provides read-only query methods. This is the
interface that `state_db_class.py` and skill stubs will use.

`ArtifactGraph` does no parsing — it receives an already-loaded
`WorkflowSchema` from `loader.load()`. Its job is to answer questions about
the graph: what phases exist, what does an artifact depend on, what gate
guards it.

## Acceptance Criteria

- [ ] `ArtifactGraph(schema: WorkflowSchema)` constructor accepts a loaded schema.
- [ ] `graph.phases() -> list[str]` returns artifact IDs in topological order (the order in `schema.artifacts` after the loader's topo-sort).
- [ ] `graph.artifact(id: str) -> ArtifactSpec` returns the artifact with the given ID; raises `KeyError` if not found.
- [ ] `graph.requires(id: str) -> list[str]` returns the direct dependency IDs for the given artifact.
- [ ] `graph.gate_for(id: str) -> GateSpec | None` returns the gate spec for the artifact, or `None` if no gate.
- [ ] `graph.instruction_for(id: str) -> str | None` returns the `instruction` field for the artifact, or `None`.
- [ ] `ArtifactGraph` is exported from `clasi/schemas/__init__.py`.
- [ ] `graph.py` imports only from `clasi.schemas` (no other `clasi.*` imports).
- [ ] `uv run pytest` passes.

## Implementation Plan

**Approach**: Build an index (`dict[str, ArtifactSpec]`) in `__init__` from
`schema.artifacts`. All query methods look up this index. `phases()` returns
`[a.id for a in schema.artifacts]` since the loader already sorted them.

**Files to modify**:
- `clasi/schemas/graph.py` — replace stub with full implementation
- `clasi/schemas/__init__.py` — add `ArtifactGraph` to exports

**Testing plan**: The end-to-end tests in ticket 013 exercise `ArtifactGraph`
via the full schemas. In this ticket, add a small unit test in
`tests/clasi/schemas/test_graph.py` with a hand-crafted two-artifact schema to
verify each query method.

**Documentation updates**: None.
