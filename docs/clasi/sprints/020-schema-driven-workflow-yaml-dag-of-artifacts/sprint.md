---
id: "020"
title: "Schema-driven workflow: YAML DAG of artifacts"
status: ticketing
branch: sprint/020-schema-driven-workflow-yaml-dag-of-artifacts
use-cases: []
source-todos:
  - schema-driven-workflow-yaml-dag.md
---

# Sprint 020: Schema-driven workflow: YAML DAG of artifacts

## Goals

Replace CLASI's hardcoded workflow with a YAML schema that declares the SE
process as a DAG of artifacts. The phase machine, skill instructions, and
team-lead dispatch logic all derive from one source of truth instead of three
independently-maintained locations that must stay in sync.

## Problem

CLASI currently encodes its workflow in three separate places:

1. The `PHASES` list in `clasi/state_db_class.py` — the SQLite phase machine.
2. Skill bodies under `clasi/plugin/skills/` — each skill carries its own
   prose about what comes before and after it.
3. Dispatch logic in `clasi/plugin/agents/team-lead/agent.md` and the `se`
   skill routing.

When a phase is added, removed, or its gate logic changes, all three locations
must be edited together or the system desyncs. The OOP escape hatch and the
recurring "skill says X but state DB enforces Y" bugs are symptoms. Two recent
sprints touched all three locations to land what was conceptually one change.

This is a single-point-of-truth problem: the workflow definition should live in
one editable file, and all enforcement, skill prose, and dispatch logic should
read from it.

## Solution outline

Introduce a `clasi/schemas/` package holding workflow definitions as YAML DAGs.
The SE process becomes `clasi/schemas/se-process/schema.yaml`. Each artifact
node declares its id, what it generates, an instruction file reference, its
`requires` dependencies, and any gate kind.

From the schema derive:
- The phase machine: `PHASES` in `state_db_class.py` becomes a topological sort
  of the schema's artifact ids plus gate ordering. Retain as a constant with a
  fallback behind a feature flag during migration.
- Skill bodies: each artifact's `instruction:` points to a markdown file
  containing the prose currently embedded in the skill. Skills become thin
  wrappers that load the instruction file.
- Dispatch routing: team-lead's "what comes next" logic reads `requires` to
  know what's blocked, what's ready, and which gate needs recording.

A second `solo-process` schema ships alongside, validating the abstraction
produces a real second workflow (leaner: overview + sprint-plan + tickets +
execution, no architecture-review, no stakeholder gates). Selection via
`clasi init --process se` (default) or `--process solo`.

Migration proceeds in six steps (schema skeleton -> lift instruction prose ->
move PHASES to derived -> move gate metadata -> add solo-process -> remove
fallback constant).

## Success criteria

- `clasi/schemas/se-process/schema.yaml` exists and declares the full SE
  process as a DAG. Loader (`clasi/schemas/loader.py`) parses, validates,
  and topo-sorts it at server startup.
- Loader rejects cycles, missing deps, unknown gate kinds, and duplicate
  artifact IDs. These are tested in CI.
- `PHASES` in `state_db_class.py` is derived from the schema (not hardcoded).
  Existing phase-machine behavior is unchanged.
- Skill bodies for `plan-sprint`, `execute-sprint`, `architecture-review`,
  `sprint-review`, and `close-sprint` load their instruction prose from
  `schemas/se-process/instructions/*.md` rather than embedding it inline.
- `clasi/schemas/solo-process/schema.yaml` exists and produces a valid leaner
  workflow. `clasi init --process solo` selects it.
- A `clasi schema validate <path>` CLI subcommand runs the loader on
  arbitrary user schemas.
- No OOP-escape-hatch usage needed to work around phase mismatches.

## In Scope

- `clasi/schemas/__init__.py`, `loader.py`, `graph.py`.
- `clasi/schemas/se-process/schema.yaml` and `instructions/*.md` files.
- `clasi/schemas/solo-process/schema.yaml` and `instructions/*.md`.
- `clasi/state_db_class.py`: derive `PHASES` from schema; keep hardcoded
  fallback behind feature flag for one release.
- Skill stub updates: `plan-sprint`, `execute-sprint`, `architecture-review`,
  `sprint-review`, `close-sprint`.
- `clasi init --process` flag.
- `clasi schema validate` CLI subcommand.
- Tests: cycle detection, missing-dep errors, topo-sort, full round-trip per
  schema, `--process solo` init.

## Out of Scope

- Schema versioning / migration tooling (`clasi schema migrate`). Document the
  limitation for v1.
- Per-project schema overrides (project-local schema.yaml shadowing the package
  default). Defer until a user asks.
- Cross-schema artifact reuse. Each schema is self-contained for v1.
- Schema editor / GUI.
- Collapsing per-artifact skill files into one `se` skill. Defer (Skill
  discovery open question).
- Solo-vs-SE switching mid-project. Document the limitation.

## Dependencies and sequencing

- Sprint 017 (two-phase tooling) should land first. The phase machine change
  in this sprint interacts with the `roadmap` phase added by 017. If 017 lands
  first, the schema-loader can include `roadmap` from the start.
- Sprint 018 (exception protocol) is independent but benefits from having
  consistent skill prose (which this sprint provides). Best after 017, before
  or alongside 018.
- Sprint 019 (clasr uninstall fix) is fully independent of this sprint.
- Sprint 021 (integration registry) is fully independent. Orthogonal domains.
- Sprint 022 (worktree process) is independent.
- This sprint is the single largest architectural change in the roadmap.
  Plan for a longer execution window than the other sprints.

## Source TODOs

- `docs/clasi/todo/schema-driven-workflow-yaml-dag.md`

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Schema package skeleton: Pydantic models and SchemaError | — |
| 002 | Schema loader: parse YAML, validate, topo-sort, cycle detection | 001 |
| 003 | ArtifactGraph: phases, artifact, requires, gate_for queries | 002 |
| 004 | Loader unit tests: every rejection branch | 002 |
| 005 | se-process/schema.yaml: full SE workflow DAG | 002 |
| 006 | Lift se-process skill prose into instructions/*.md files | 005 |
| 007 | Reduce skill SKILL.md files to stub loaders | 006 |
| 008 | state_db_class.py: derive PHASES from schema behind feature flag | 003, 005 |
| 009 | Remove PHASES feature flag: make schema-derived path unconditional | 008 |
| 010 | clasi schema validate CLI subcommand | 002 |
| 011 | solo-process/schema.yaml: leaner solo workflow DAG | 002 |
| 012 | clasi init --process flag and config.yaml process key | 010, 011 |
| 013 | End-to-end tests: se-process and solo-process round-trips | 009, 012 |
