---
id: "D"
title: "Schema-driven workflow — YAML DAG of artifacts"
status: planning
branch: sprint/D-schema-driven-workflow
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint D: Schema-driven workflow — YAML DAG of artifacts

## Goals

Replace CLASI's hardcoded workflow with a YAML schema that declares the SE process as a DAG of artifacts. The phase machine, skill instructions, and team-lead dispatch logic all derive from one source of truth instead of three.

## Problem

CLASI currently encodes its workflow in three places that have to stay in sync:

1. The `PHASES` list in `clasi/state_db_class.py` (the SQLite phase machine).
2. The skill bodies under `clasi/plugin/skills/` — `plan-sprint`, `execute-sprint`, `close-sprint`, `architecture-review`, `sprint-review`. Each carries its own prose about what comes before and after it.
3. The dispatch logic in `clasi/plugin/agents/team-lead/agent.md` and the routing in the `se` skill.

When a phase is added/removed or a gate changes, all three have to be edited together. The OOP escape hatch and the recurring "skill says X but state DB enforces Y" bugs are symptoms of this. Two recent sprints touched all three locations to land conceptually one change.

OpenSpec's OPSX rewrite solved this by promoting the workflow definition into an editable `schemas/spec-driven/schema.yaml`. Slash commands, instruction prompts, completion detection, and dependency resolution all read from the schema. Adding an artifact or rewiring an edge is a schema edit, not a code change.

## Solution

1. **Schema package skeleton + loader** — `clasi/schemas/loader.py`, `graph.py`, with pydantic models for artifact, gate, schema. Cycle detection. Loader is the only path that reads schemas; nothing else parses YAML directly.
2. **`clasi/schemas/se-process/schema.yaml`** — declares the SE workflow as a DAG: overview → specification, usecases → sprint-plan → architecture-delta → tickets → execution → close. Each artifact carries `requires:`, optional `gate:`, optional `lock:`. After Sprint B, `architecture-delta` slots in cleanly.
3. **Lift instruction prose** out of each workflow skill into `clasi/schemas/se-process/instructions/*.md`. Skills become thin wrappers that load the instruction file plus the schema-derived next-step pointer.
4. **Move PHASES to derived** — `state_db_class.py` reads phases from the active schema. Gate kinds and recorded names move from scattered call sites into `gate:` blocks.
5. **Add `clasi/schemas/solo-process/schema.yaml`** — leaner DAG (overview + sprint-plan + tickets + execution; no architecture-review, no stakeholder gate). Selection is a project-init flag: `clasi init --process se` (default) or `--process solo`.
6. **`clasi schema validate <path>` CLI subcommand** — runs the loader on arbitrary schemas (groundwork for community presets).
7. **Remove the fallback constant** once both schemas have shipped one release without regressions.

## What stays as code

The schema declares *what* the workflow is, not *how* gates enforce. Keep in Python:
- The execution lock (`acquire_execution_lock`).
- Server-side gate validation (`record_gate_result`, `review_sprint_pre_execution`).
- The dispatch log and tool-call tracing.
- File system mutations.

OpenSpec lost gate enforcement by going purely declarative; we keep it. The schema is read at server startup and held as an in-memory graph; tools resolve artifact IDs to enforcement code.

## Success Criteria

- `clasi/schemas/` package present with loader + graph + pydantic models.
- Loader rejects: cycles, missing deps, unknown gate kinds, duplicate artifact IDs. Every rejection has a test.
- `clasi/schemas/se-process/schema.yaml` exists and matches the current phase machine; running CLASI produces identical phase sequencing.
- Skills load instructions via the loader; skill bodies are short stubs.
- `state_db_class.py` derives `PHASES` from the schema (constant retained one release as fallback behind a feature flag).
- `clasi/schemas/solo-process/schema.yaml` exists and `clasi init --process solo` initializes a project against it.
- `clasi schema validate <path>` works on user-supplied schemas.
- Full SE workflow runs unchanged for a synthetic sprint under both schemas.

## Scope

### In Scope

- Schema package, loader, validator, graph queries.
- Two ship-default schemas: SE-process and solo-process.
- Skill bodies refactored to load instruction files.
- Phase-machine derivation.
- Gate-kind dispatch table.
- `--process` flag on `clasi init`.
- `clasi schema validate` CLI.

### Out of Scope

- Schema editor / GUI.
- Per-project schema overrides (project-local `schema.yaml` shadowing). Defer until requested.
- Cross-schema artifact reuse — each schema is self-contained for v1.
- Schema migrations between versions — `version: 1` for now; `clasi schema migrate` deferred.
- Solo-vs-SE switching mid-project — out of scope; document as a limitation.
- Per-ticket gate kind treated specially (open question; resolve during ticketing — recommend modeling tickets as their own artifact nodes generated at ticket-creation time, but defer if scope grows).

## Test Strategy

- Unit tests for loader: each rejection branch.
- Unit tests for graph queries: ready/blocked/done across synthetic schemas.
- Snapshot test: the shipped schemas load without errors and produce expected DAG.
- Integration test: full sprint walked end-to-end with the SE schema; same with the solo schema.
- Regression test: skills still produce the same output under the new load path as under the old inlined-prose path.

## Architecture impact

Largest architectural TODO in the queue. After it lands:
- Workflow becomes data, not code, for everything except gate enforcement.
- Adding a phase or rewiring an edge is a YAML edit + an instruction file.
- The OOP escape and the recurring desync bugs disappear because there's one source of truth.

## Dependencies / sequencing notes

- After Sprint A — paths must be pinned at `.clasi/` before being baked into schemas.
- After Sprint B — schema declares `architecture-delta` (not `architecture-update`); landing delta first means the schema doesn't have to encode legacy artifact names.
- Independent of Sprints C, E, F.

## Source TODO

- `schema-driven-workflow-yaml-dag.md` (as-is)
