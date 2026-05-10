---
id: '011'
title: 'solo-process/schema.yaml: leaner solo workflow DAG'
status: done
use-cases:
- SUC-001
- SUC-006
depends-on:
- '002'
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# solo-process/schema.yaml: leaner solo workflow DAG

## Description

Write `clasi/schemas/solo-process/schema.yaml` — the leaner workflow for solo
developers. The DAG omits `architecture-review` and `stakeholder-review`
phases and their gates. The phase sequence is: `roadmap`, `planning-docs`,
`ticketing`, `executing`, `closing`, `done`.

Also create `clasi/schemas/solo-process/instructions/` with stub instruction
files for each artifact. Solo-process instruction content will be tailored
for a single developer working without team gates.

This schema validates that the abstraction is real: a completely different
phase list, no gate kinds except `per-ticket`, loads and topo-sorts
correctly through the same loader.

## Acceptance Criteria

- [x] `clasi/schemas/solo-process/schema.yaml` exists and loads via `loader.load()`.
- [x] `ArtifactGraph(schema).phases()` returns `["roadmap", "planning-docs", "ticketing", "executing", "closing", "done"]`.
- [x] No `architecture-review` or `stakeholder-review` artifact nodes exist in the solo schema.
- [x] No `gate.kind: review` or `gate.kind: stakeholder-review` gates exist in the solo schema.
- [x] `executing` artifact still has `gate.kind: per-ticket` and `lock: execution`.
- [x] Instruction stub files exist for each artifact: `overview.md`, `sprint-plan.md`, `tickets.md`, `execution.md`, `close.md`.
- [x] `pyproject.toml` package data config already covers `clasi/schemas/**/*` (from ticket 005; no change needed).
- [x] `uv run pytest` passes.

## Implementation Plan

**Approach**: Write the YAML following the architecture-update.md template for
solo-process. Verify by running `clasi schema validate clasi/schemas/solo-process/schema.yaml`
(using the CLI from ticket 010, or calling `loader.load()` directly).

**Files to create**:
- `clasi/schemas/solo-process/schema.yaml`
- `clasi/schemas/solo-process/__init__.py` (empty, for package data)
- `clasi/schemas/solo-process/instructions/overview.md` (stub)
- `clasi/schemas/solo-process/instructions/sprint-plan.md` (stub)
- `clasi/schemas/solo-process/instructions/tickets.md` (stub)
- `clasi/schemas/solo-process/instructions/execution.md` (stub)
- `clasi/schemas/solo-process/instructions/close.md` (stub)

**Testing plan**: Add a smoke test in `tests/clasi/schemas/test_solo_schema.py`:
`assert loader.load(...).name == "solo-process"` and
`assert ArtifactGraph(schema).phases() == ["roadmap", "planning-docs", "ticketing", "executing", "closing", "done"]`.

**Documentation updates**: None.
