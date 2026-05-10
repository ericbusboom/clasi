---
status: in-progress
sprint: '020'
tickets:
- 020-001
---

# Schema-driven workflow definition — YAML DAG of artifacts

Replace CLASI's hardcoded workflow with a YAML schema that declares
the SE process as a DAG of artifacts. The phase machine, the skill
instructions, and the team-lead dispatch logic all derive from one
source of truth instead of three.

## Why we cared

CLASI currently encodes its workflow in three places that have to
stay in sync:

1. The `PHASES` list in `clasi/state_db_class.py` — the SQLite phase
   machine (`planning-docs → architecture-review → … → done`).
2. The skill bodies under `clasi/plugin/skills/` — `plan-sprint`,
   `execute-sprint`, `close-sprint`, `architecture-review`,
   `sprint-review`, etc. Each skill carries its own prose about
   what comes before and after it.
3. The dispatch logic in `clasi/plugin/agents/team-lead/agent.md`
   and the routing in the `se` skill.

When a phase is added, removed, or its gate logic changes, all three
have to be edited together or the system desyncs. The OOP escape
hatch and the recurring "skill says X but state DB enforces Y" bugs
are symptoms of this. Two recent sprints touched all three locations
to land what was conceptually one change.

OpenSpec's recent OPSX rewrite solved exactly this by promoting the
workflow definition out of TypeScript and into an editable
`schemas/spec-driven/schema.yaml`. Slash commands, instruction
prompts, completion detection, and dependency resolution all read
from the schema. Adding an artifact or rewiring an edge is a
schema edit, not a code change.

## Proposed shape

A new directory `clasi/schemas/` holds workflow definitions. The SE
process becomes `clasi/schemas/se-process/schema.yaml`:

```yaml
version: 1
name: se-process
description: Full software-engineering process — team mode

artifacts:
  - id: overview
    generates: docs/design/overview.md
    template: se-overview-template.md
    instruction: clasi/schemas/se-process/instructions/overview.md
    requires: []

  - id: specification
    generates: docs/design/specification.md
    template: se-specification-template.md
    instruction: clasi/schemas/se-process/instructions/specification.md
    requires: [overview]

  - id: usecases
    generates: docs/design/usecases.md
    requires: [overview]

  - id: sprint-plan
    generates: docs/clasi/sprints/<id>/sprint.md
    requires: [overview, specification, usecases]
    gate:
      kind: stakeholder-review
      record: gate.planning-docs

  - id: architecture-update
    generates: docs/clasi/sprints/<id>/architecture-update.md
    requires: [sprint-plan]
    gate:
      kind: review
      reviewer: architecture-reviewer
      record: gate.architecture-review

  - id: tickets
    generates: docs/clasi/sprints/<id>/tickets/
    requires: [sprint-plan, architecture-update]
    gate:
      kind: stakeholder-review
      record: gate.stakeholder-review

  - id: execution
    generates: <code + test changes>
    requires: [tickets]
    lock: execution
    gate:
      kind: per-ticket
      record: gate.ticket-complete

  - id: close
    generates: docs/clasi/sprints/done/<id>/
    requires: [execution]
```

A second schema `clasi/schemas/solo-process/schema.yaml` ships
alongside, declaring a leaner DAG (overview + sprint-plan + tickets +
execution, no architecture-review, no stakeholder gates). Selection
is a project-init flag: `clasi init --process se` (default) or
`--process solo`.

## What derives from the schema

- **The phase machine.** `state_db_class.py`'s `PHASES` becomes
  computed from `artifacts[].id` ordered by topological sort plus
  the explicit gates. Phase transitions remain server-validated; the
  schema just supplies the list.
- **Skill bodies.** Each artifact's `instruction:` field points at a
  markdown file containing the prose currently embedded in the
  matching skill. Skills become thin wrappers that load the
  instruction file plus the schema-derived next-step pointer.
- **Dispatch routing.** Team-lead's "what comes next" logic reads
  `requires` to know what's blocked, what's ready, and which gate
  needs recording before advancing.
- **Artifact-tools surface.** `create_sprint`, `record_gate_result`,
  `advance_sprint_phase` keep their signatures but consult the
  schema instead of hardcoded constants.

## What stays as code

The schema declares *what* the workflow is, not *how* the gates
enforce it. Keep in Python:

- The execution lock (`acquire_execution_lock`).
- Server-side gate validation (`record_gate_result`,
  `review_sprint_pre_execution`).
- The dispatch log and tool-call tracing.
- File system mutations.

OpenSpec lost gate enforcement by going purely declarative; we keep
it. The schema is read at server startup and held as an in-memory
graph; tools resolve artifact IDs to enforcement code.

## Module layout

```
clasi/
  schemas/
    __init__.py
    loader.py              ← parse + validate (pydantic), topo-sort,
                              cycle detection, gate-kind registry
    graph.py               ← ArtifactGraph: ready/blocked/done queries
    se-process/
      schema.yaml
      instructions/
        overview.md
        specification.md
        usecases.md
        sprint-plan.md
        architecture-update.md
        tickets.md
        execution.md
        close.md
    solo-process/
      schema.yaml
      instructions/...
```

`loader.py` owes existing tests for cycle detection and missing-
dependency errors before any production code reads from it.

## Migration sequence

1. **Schema package skeleton + loader + tests.** Pydantic models for
   artifact, gate, schema. Cycle detection. No callers yet.
2. **Lift instruction prose** out of `plan-sprint`, `execute-sprint`,
   `architecture-review`, `sprint-review`, `close-sprint` skills
   into `instructions/*.md`. Skills load them via the loader. Skill
   bodies shrink to a stub plus the load call. Behaviour unchanged.
3. **Move PHASES to derived.** `state_db_class.py` reads phases from
   the active schema instead of a constant. Keep the constant as a
   fallback for one release behind a feature flag.
4. **Move gate metadata to schema.** Gate kinds and their recorded
   names move from scattered call sites to `gate:` blocks in the
   schema. Enforcement code dispatches on `gate.kind`.
5. **Add solo-process schema** and `--process` flag to `clasi init`.
   Validates the abstraction by producing a real second workflow.
6. **Remove the fallback constant** once both schemas have shipped
   one release without regressions.

## Validation

- Loader rejects cycles, missing deps, unknown gate kinds, duplicate
  artifact IDs.
- Loader is the only path that reads schemas; nothing else parses
  YAML directly.
- Schema files ship as package data; tests load them in CI.
- A `clasi schema validate <path>` CLI subcommand runs the loader on
  arbitrary user schemas (groundwork for community presets).

## Open questions

- **Schema versioning.** First field is `version: 1`. When the
  schema shape changes (new gate kinds, new fields), do we bump and
  migrate, or accept the schema as forever-1? Suggest: migrate via
  a `clasi schema migrate` step similar to how `alembic` runs.
- **Per-ticket gate kind.** `execution`'s gate is "per-ticket close"
  — that doesn't fit cleanly into a single record. Either model
  tickets as their own artifact (one node per ticket, generated at
  ticket-creation time) or special-case `kind: per-ticket`. The
  former is more honest but harder to schema-validate ahead of time.
- **Skill discovery.** Today skills are auto-loaded from
  `.claude/skills/`. If skill bodies become stubs that delegate to
  schema-driven instructions, do we keep one skill per artifact
  (current shape) or collapse to one `se` skill that takes an
  artifact ID arg? Current shape is more discoverable; collapsed
  shape removes per-artifact skill files. Defer.
- **Solo vs SE switching mid-project.** A project initialised with
  `--process solo` may want to graduate to `--process se`. Schema
  swap is a state-DB migration question, not a schema-loader one.
  Out of scope for v1; document the limitation.

## Out of scope

- A schema editor / GUI. Power users edit YAML.
- Per-project schema overrides (project-local schema.yaml shadowing
  the package default). Useful eventually; defer until at least one
  user asks.
- Cross-schema artifact reuse. Each schema is self-contained for v1.

## Related work in flight

The in-progress `clasr` work (sprint 014) moves the per-platform
*install* surface to a renderer-driven design. Schema-driven workflow
is the analogous move for the *workflow* surface. They're
orthogonal — clasr is about where files land per platform, schemas
are about which artifacts the SE process produces. They share a
spirit (declarative source, code as renderer) but no shared code.

## Origin

Comparative analysis of CLASI vs github/spec-kit vs Fission-AI/
OpenSpec, 2026-05-07
(`clasi-spec-kit-openspec-analysis.md`). Stakeholder pulled the
top three suggestions out of that analysis. This is suggestion #1,
ranked first by the analysis as "the single biggest architectural
win in OpenSpec" and "if only one change: this one."
