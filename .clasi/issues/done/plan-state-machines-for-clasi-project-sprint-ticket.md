---
status: done
---

# Plan: State Machines for CLASI (Project / Sprint / Ticket)

## Context

CLASI's process artifacts (project, sprint, ticket) currently have implicit states scattered across `clasi/schemas/se-process/schema.yaml`, `clasi/state_db_class.py`, `clasi/ticket.py`, and the markdown templates. There is no single document that says *what states exist, what the transition conditions are, and how you tell which state you are in*. Without that, both humans and agents have to infer state from a mix of frontmatter, file locations, branch name, and lock files.

This task adds a single authoritative design document under `docs/design/` that:

1. Defines three state machines (Project, Sprint, Ticket) with named transitions and named conditions.
2. Renders each as a Mermaid `stateDiagram-v2`.
3. Provides a YAML description of each machine (states, transitions, conditions) so it can later become the input for schema generation.
4. Narratively maps the (target) 5-state Sprint model onto the existing 8-phase `schema.yaml` and flags the divergence as a future reconciliation item.

**Scope is docs-only.** No edits to `schema.yaml`, templates, or `state_db_class.py` in this pass. A follow-on sprint will reconcile.

## Target deliverable

One new file: `docs/design/state-machines.md`.

Structure:

1. **Introduction** — purpose; why states matter; one-paragraph summary of the three machines.
2. **Project state machine** — Mermaid diagram + YAML block + condition definitions.
3. **Sprint state machine** — Mermaid diagram + YAML block + condition definitions + transition rules table.
4. **Ticket state machine** — Mermaid diagram + YAML block + condition definitions.
5. **Cross-machine invariants** — rules that span machines (e.g. sprint cannot enter `review` while any ticket is not `done`; project enters `in-sprint` iff exactly one sprint is `executing`).
6. **Mapping to current implementation** — narrative table mapping the target 5-state Sprint model to the existing 8-phase `schema.yaml`. Calls out divergence and notes "out-of-process" as a future design question (no encoding yet).

## State machines to specify

### 1. Project state machine (flat states)

States: `uninitialized`, `planning`, `in-sprint`.

- **`uninitialized`** — no `docs/design/overview.md` (or whichever overview path is canonical; verify against `clasi/schemas/se-process/schema.yaml` line 9 which says `docs/clasi/overview.md`). Plan will use the schema's path as authoritative.
- **`planning`** — overview exists, currently on `master` (or main), no sprint branch checked out / no execution lock held.
- **`in-sprint`** — currently on a `sprint/<id>-<slug>` branch with an active execution lock (one sprint executing at a time).

Transitions (named):

- `initialize`: `uninitialized → planning` — condition `overview_exists`.
- `enter-sprint`: `planning → in-sprint` — conditions `on_sprint_branch`, `execution_lock_held`, `sprint_status_executing`.
- `exit-sprint`: `in-sprint → planning` — conditions `execution_lock_released`, `back_on_master`.

### 2. Sprint state machine (5 states, target model)

States: `open`, `planned`, `ticketed`, `executing`, `review`, `closed`.

- **`open`** — `sprint.md` exists with `id`, `title`, `status: open`. No architecture or usecases yet.
- **`planned`** — `sprint.md`, `architecture-update.md` (or per-current-naming: architecture artifact), and a use-cases artifact all present. No tickets yet.
- **`ticketed`** — all planning artifacts present, plus at least one ticket file in `tickets/`. Not yet executing.
- **`executing`** — sprint has acquired execution lock; on its sprint branch; programmer agents may pick up tickets.
- **`review`** — all tickets in this sprint are `done`; close-report not yet written / sprint-review not yet passed.
- **`closed`** — sprint reviewed and merged; `close-report.md` present; lock released.

Transitions (named) and conditions:

- `plan`: `open → planned` — `architecture_present`, `usecases_present`, `architecture_review_recorded`.
- `ticket`: `planned → ticketed` — `at_least_one_ticket`, `stakeholder_approval_recorded`.
- `execute`: `ticketed → executing` — `execution_lock_acquired`, `on_sprint_branch`, `no_other_sprint_executing`.
- `complete`: `executing → review` — `all_tickets_done`.
- `close`: `review → closed` — `close_report_present`, `sprint_review_passed`, `branch_merged`.

### 3. Ticket state machine

States: `open`, `in-progress`, `done`. (Plus an off-axis `exception` state — keep it as a labeled sub-state that can be entered from `in-progress` and exited back to `in-progress` or escalated.)

Transitions (named):

- `start`: `open → in-progress` — `sprint_executing`, `dependencies_done`, `ticket_assigned_to_agent`.
- `finish`: `in-progress → done` — `acceptance_criteria_met`, `tests_pass`, `moved_to_done_dir`.
- `throw`: `in-progress → exception` — `exception_block_written`.
- `recover`: `exception → in-progress` — `exception_block_cleared`.
- `reopen`: `done → open` — `reopen_requested` (rare; supported by `reopen_ticket` MCP tool).

## YAML shape (per machine)

Each machine block in the doc will look like:

```yaml
machine: sprint
initial: open
states: [open, planned, ticketed, executing, review, closed]
transitions:
  - name: plan
    from: open
    to: planned
    conditions: [architecture_present, usecases_present, architecture_review_recorded]
  - name: ticket
    from: planned
    to: ticketed
    conditions: [at_least_one_ticket, stakeholder_approval_recorded]
  # ...
conditions:
  architecture_present:
    description: docs/clasi/sprints/<id>/architecture-update.md exists
    check: file-exists
  architecture_review_recorded:
    description: state DB has architecture_review gate recorded for this sprint
    check: state-db
  # ...
```

The intent of the YAML is to be a future-machine-readable spec — but in this sprint we are only writing it for humans.

## Critical files

Files to **read** while drafting (not modify):

- `clasi/schemas/se-process/schema.yaml` — current 8-phase model + gate records (lines 1–64).
- `clasi/state_db_class.py:74-82` — `_GATE_REQUIREMENTS`, source of truth for which phases gate on which records.
- `clasi/state_db_class.py:212-276` — `advance_phase()`, the current transition validator.
- `clasi/ticket.py:36-42, 123-141` — ticket status getter/setter and `move_to_done()`.
- `clasi/templates/sprint.md:1-7` — sprint frontmatter (note: current initial `status: roadmap`, not `open`).
- `clasi/templates/ticket.md:1-22` — ticket frontmatter (current initial `status: open`; confirms ticket model).
- `docs/design/overview.md`, `docs/design/usecases.md` — Mermaid + section style reference.
- `docs/clasi/architecture/architecture-update-022.md:56-99` — existing worktree state-machine example to follow.

Files to **create**:

- `docs/design/state-machines.md` — the deliverable.

## Mapping section (the "document both" answer)

A table in the new doc mapping target sprint states ↔ current `schema.yaml` phases, roughly:

| Target state (this doc) | Current phase(s) in `schema.yaml` |
|-------------------------|-----------------------------------|
| `open` | `roadmap` (sprint exists with title only) |
| `planned` | `planning-docs` + `architecture-review` + `stakeholder-review` collapsed |
| `ticketed` | `ticketing` |
| `executing` | `executing` |
| `review` | (no explicit phase today — implicit between last ticket done and `closing`) |
| `closed` | `closing` → `done` |

Followed by a short paragraph noting that the divergence (especially the collapsed planning phases and the missing explicit `review` state) is a known reconciliation item, deferred to a future sprint, and out of scope for this design doc.

## Verification

- Open `docs/design/state-machines.md` in a Mermaid-rendering preview (e.g. VS Code Markdown preview) and confirm all three diagrams render.
- Lint the embedded YAML blocks by piping each through `python -c "import yaml,sys; yaml.safe_load(sys.stdin.read())"` (or equivalent) to confirm they parse.
- Cross-check the mapping table: for each row, verify the listed current phase actually appears in `clasi/schemas/se-process/schema.yaml`.
- Cross-check condition names: every condition referenced in a `transitions` list must have a definition in the `conditions` block of the same YAML machine.
- No code, schema, or template files are modified in this sprint.

## Explicitly out of scope

- Modifying `clasi/schemas/se-process/schema.yaml`.
- Modifying `clasi/state_db_class.py`, `clasi/ticket.py`, or any MCP tool.
- Modifying `clasi/templates/sprint.md` or `clasi/templates/ticket.md`.
- Designing the out-of-process re-imagining (will get its own TODO/sprint later — the doc will note this as a known open question, not solve it).
- Producing a TODO to track the reconciliation work (user chose docs-only).
