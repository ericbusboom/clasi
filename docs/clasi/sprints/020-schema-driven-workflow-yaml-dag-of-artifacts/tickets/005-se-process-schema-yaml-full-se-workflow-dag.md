---
id: "005"
title: "se-process/schema.yaml: full SE workflow DAG"
status: todo
use-cases: [SUC-001, SUC-003]
depends-on: ["002"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# se-process/schema.yaml: full SE workflow DAG

## Description

Write `clasi/schemas/se-process/schema.yaml` — the YAML declaration of the
full SE workflow as a DAG. The artifact IDs must match the current `PHASES`
list in `state_db_class.py` exactly: `roadmap`, `planning-docs`,
`architecture-review`, `stakeholder-review`, `ticketing`, `executing`,
`closing`, `done`.

`roadmap` is declared first (as required by sprint 017 context). Each
artifact has a `generates` description, an `instruction` file reference, and
`requires` dependencies. The two gate-bearing artifacts are `architecture-review`
(gate kind `review`, record `architecture_review`) and `stakeholder-review`
(gate kind `stakeholder-review`, record `stakeholder_approval`). The
`executing` artifact has gate kind `per-ticket`.

Also create the `clasi/schemas/se-process/instructions/` directory and stub
`.md` files for each artifact (8 files). The stub files contain a single line
`# <artifact-id> instructions — to be filled in by ticket 006`. The actual
prose is lifted in ticket 006.

Ensure the package data configuration in `pyproject.toml` includes
`clasi/schemas/**/*` so schema files ship with the installed package.

## Acceptance Criteria

- [ ] `clasi/schemas/se-process/schema.yaml` exists and is valid per `loader.load()`.
- [ ] Artifact IDs in the schema, in topo-sort order, produce exactly `["roadmap", "planning-docs", "architecture-review", "stakeholder-review", "ticketing", "executing", "closing", "done"]`.
- [ ] `architecture-review` artifact has `gate.kind: review` and `gate.record: architecture_review`.
- [ ] `stakeholder-review` artifact has `gate.kind: stakeholder-review` and `gate.record: stakeholder_approval`.
- [ ] `executing` artifact has `gate.kind: per-ticket` and `lock: execution`.
- [ ] All 8 instruction stub files exist under `clasi/schemas/se-process/instructions/`.
- [ ] `pyproject.toml` package data config includes `clasi/schemas/**/*`.
- [ ] `uv run pytest` passes.

## Implementation Plan

**Approach**: Write the YAML by hand following the architecture-update.md
schema template. Run `python -c "from clasi.schemas import loader; print(loader.load('clasi/schemas/se-process/schema.yaml').artifacts)"` to verify it loads. Check the topo-sort output matches `PHASES`.

**Files to create**:
- `clasi/schemas/se-process/schema.yaml`
- `clasi/schemas/se-process/instructions/overview.md` (stub)
- `clasi/schemas/se-process/instructions/specification.md` (stub)
- `clasi/schemas/se-process/instructions/usecases.md` (stub)
- `clasi/schemas/se-process/instructions/sprint-plan.md` (stub)
- `clasi/schemas/se-process/instructions/architecture-update.md` (stub)
- `clasi/schemas/se-process/instructions/tickets.md` (stub)
- `clasi/schemas/se-process/instructions/execution.md` (stub)
- `clasi/schemas/se-process/instructions/close.md` (stub)

**Files to modify**:
- `pyproject.toml` — add `clasi/schemas/**/*` to `[tool.setuptools.package-data]` or equivalent

**Testing plan**: The end-to-end test in ticket 013 loads this schema. In this
ticket, write a single smoke test in `tests/clasi/schemas/test_se_schema.py`:
`assert loader.load("clasi/schemas/se-process/schema.yaml").name == "se-process"`.

**Documentation updates**: None.
