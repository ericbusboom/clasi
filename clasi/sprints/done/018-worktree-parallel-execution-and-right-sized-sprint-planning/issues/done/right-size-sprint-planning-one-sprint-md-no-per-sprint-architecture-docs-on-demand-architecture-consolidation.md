---
status: done
sprint: 018
tickets:
- 018-002
- 018-003
- 018-004
- 018-005
- 018-012
- 018-013
- 018-014
- 018-015
---

# Right-size sprint planning: one sprint.md, no per-sprint architecture docs, on-demand architecture consolidation

## Context

CLASI currently forces every sprint through a heavy three-document planning model — `sprint.md` +
`usecases.md` + `architecture-update.md` — plus a mandatory architecture-review gate, and it copies
each sprint's architecture-update into a growing `docs/architecture/` pile. For small features this is
massive overkill (the e2e review, `clasi/issues/e2e-001-review.md` #1 and #8, documents 3,500–4,000
word plans with Mermaid diagrams for 40-line modules, and near-identical architecture-update files
restating the whole structure each sprint). A string of per-sprint architecture updates also never
gives you a single coordinated picture of the architecture.

**Goal:** let the sprint-planner size planning effort to the feature; collapse use cases + architecture
into right-sized **sections of a single `sprint.md`**; stop generating/accumulating per-sprint
architecture-update documents; and produce the *coordinated* architecture **on demand** (read prior
sprint docs + current code → one consolidated doc), not as an automatic per-sprint byproduct.

Confirmed decisions: the consolidated architecture lives at a single **`docs/design/architecture.md`**,
produced on demand; the architecture-review gate becomes **optional/skippable** (full review only when
a sprint introduces real architecture, recorded as skipped/N-A otherwise). This document is an
analysis/recommendation issue → planned into a sprint when the developer chooses.

## Part 1 — One `sprint.md` (use cases + architecture become right-sized sections)

- **Template:** fold the `sprint-usecases.md` and `architecture-update.md` template bodies into
  `src/clasi/templates/sprint.md` as `## Architecture` and `## Use Cases` sections (with a one-line
  note that each is sized to the change and may be "N/A — trivial"). Remove the separate template
  files and their loaders in `src/clasi/templates.py` (`SPRINT_USECASES_TEMPLATE`,
  `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`, `SPRINT_ARCHITECTURE_TEMPLATE`).
- **Scaffolding:** `Sprint.detail_promote()` ([src/clasi/sprint.py](src/clasi/sprint.py)) stops writing
  `usecases.md`/`architecture-update.md` — it scaffolds only `tickets/` + `tickets/done/` (sprint.md
  already exists from `create_sprint`, now with the merged sections). Same removal in `insert_sprint`
  ([src/clasi/tools/artifact_tools.py](src/clasi/tools/artifact_tools.py)).
- **Sprint properties / serialization:** keep `sprint_md` (and keep *read-only* `usecases`/`architecture`
  accessors so historical closed sprints still render). Drop the two files from `Sprint.to_dict()` "files",
  from the `_renumber_sprint_dir` reference-rewrite loop, and from
  `dispatch_log.py::_auto_context_documents` (subagent context becomes `sprint.md` + the ticket).

## Part 2 — State machine + gates

- **Drop the separate-file invariants** in `src/clasi/schemas/state-machines/sprint.yaml`: remove
  `is_architecture_present` and `is_usecases_present` from the `planned`, `pre-flight`, and `ticketed`
  states. `is_sprint_doc_present` still gates everything. Delete those two predicates in
  `src/clasi/state_machine/predicates/sprint.py` (and the reader calls) or repoint them at a section
  check — simplest is to delete them since planning lives in `sprint.md`.
- **Architecture-review gate → optional/skippable.** Keep the gate mechanism (`_GATE_REQUIREMENTS`,
  `is_architecture_review_recorded` just checks a record exists), but instruct the planner to **record
  the gate as `skipped`/`n-a` for small sprints** and run a full review only when the sprint introduces
  real architecture. No structural state-machine change needed — a skipped record satisfies the gate.
- **SE-process schema** (`src/clasi/schemas/se-process/schema.yaml`): change the `planning-docs` and
  `architecture-review` artifacts' `generates:` from the separate files to `sprint.md` (its sections);
  point the architecture-review instruction at reviewing the sprint.md architecture section.
- **Pre-close validation** (`review_sprint_pre_close` in artifact_tools.py): remove `usecases.md` and
  `architecture-update.md` from the `planning_docs_pre_close` list — validate only `sprint.md`
  (non-draft, no placeholder). (This also removes the recurring "status: draft" close friction.)

## Part 3 — Planning agents/skills + right-sizing

- **sprint-planner** (`agent.md`, `plan-sprint.md`, `dispatch-template.md.j2`, `contract.yaml`): author
  ONE `sprint.md` with Architecture + Use Cases as **right-sized sections**, and make an explicit
  effort decision by feature size. Guidance (planner judgment, not a hard rule): trivial/small (doc-only,
  roughly <5 files, no new modules/interfaces) → minimal sprint.md, one-line or omitted Architecture/Use
  Cases, **skip** the architecture review (record skipped); substantial/structural → full sections + a
  real architecture review. Stop mandating separate `usecases.md`/`architecture-update.md`.
- **architecture-authoring skill:** reframe to "write the architecture *section* of sprint.md, sized to
  the change, or skip"; drop the `architecture-update-rN.md` separate-file revision convention (revise
  the section in place).
- **architecture-review skill:** review the sprint.md architecture section; explicitly skippable.
- **create-tickets:** derive tickets from `sprint.md` (not separate files).
- Update the cross-references in `software-engineering.md`, `subagent-protocol.md`,
  `team-lead/agent.md`, `programmer/agent.md`, `project-status.md`, and the schema instructions
  (`sprint-plan.md`, `architecture-update.md`).

## Part 4 — On-demand architecture consolidation; remove docs/architecture

- **Repoint `consolidate-architecture`** (`src/clasi/plugin/skills/consolidate-architecture/SKILL.md`):
  instead of reading `docs/architecture/architecture-update-NNN.md`, it reads the **sprint docs**
  (`clasi/sprints/**` incl. `done/`, the Architecture sections) **+ the current code**, and writes a
  single coordinated **`docs/design/architecture.md`**. Run on demand only (the developer asks).
- **Remove the per-sprint accumulation:** delete the copy-to-`docs/architecture/` step in
  `Sprint.archive()` ([src/clasi/sprint.py](src/clasi/sprint.py)).
- **Delete `docs/architecture/`** from this repo (the 17 `architecture-update-*.md` files).

## Part 5 — Config / paths / role-guard

- `ARTIFACT_PATH_DEFAULTS` ([src/clasi/project.py](src/clasi/project.py)): remove the `architecture`
  key (`docs/architecture`); the consolidated doc lives under `design_dir` (`docs/design/architecture.md`).
- Remove/repurpose the `Project.architecture_dir` property and drop the `architecture_dir` entry from
  the role-guard `_allow_prefixes` in `src/clasi/hook_handlers.py` (`design_dir` already covers
  `docs/design/`).

## Part 6 — Backward compatibility + dogfood

- **Historical sprints stay as-is:** closed sprints (001–017) keep their existing `usecases.md`/
  `architecture-update.md` — don't rewrite history. Keep read-only accessors so they still render; the
  new model applies to new sprints. Since the invariants are dropped, old sprints still validate.
- Delete this repo's `docs/architecture/` per Part 4. Optionally (separate, on-demand) generate the
  first `docs/design/architecture.md` via the repointed consolidate-architecture.

## Affected files (representative)

- [src/clasi/templates/sprint.md](src/clasi/templates/sprint.md) (+ remove `sprint-usecases.md`, `architecture-update.md`, `sprint-architecture.md` templates); [src/clasi/templates.py](src/clasi/templates.py).
- [src/clasi/sprint.py](src/clasi/sprint.py) (`detail_promote`, `archive`, properties, `to_dict`); [src/clasi/tools/artifact_tools.py](src/clasi/tools/artifact_tools.py) (`insert_sprint`, `_renumber_sprint_dir`, `review_sprint_pre_close`); [src/clasi/dispatch_log.py](src/clasi/dispatch_log.py).
- [src/clasi/schemas/state-machines/sprint.yaml](src/clasi/schemas/state-machines/sprint.yaml), [src/clasi/state_machine/predicates/sprint.py](src/clasi/state_machine/predicates/sprint.py), [src/clasi/schemas/se-process/schema.yaml](src/clasi/schemas/se-process/schema.yaml) + `se-process/instructions/`.
- [src/clasi/project.py](src/clasi/project.py) (`ARTIFACT_PATH_DEFAULTS`, `architecture_dir`); [src/clasi/hook_handlers.py](src/clasi/hook_handlers.py) (role-guard prefixes).
- `src/clasi/plugin/agents/sprint-planner/*`, `src/clasi/plugin/skills/{architecture-authoring,architecture-review,consolidate-architecture,create-tickets,plan-sprint}/SKILL.md`, and the cross-referencing instruction/agent docs.
- Delete `docs/architecture/`. Tests across `tests/` that assert on the two files, the dropped invariants, pre-close checks, dispatch context, and templates.

## Verification

1. **Single-doc planning:** `create_sprint` + `detail_sprint` produce a `sprint.md` with Architecture/Use Cases sections and `tickets/` — and **no** `usecases.md`/`architecture-update.md`. `get_status` advances a sprint roadmap → planned → pre-flight → ticketed with only `sprint.md` present.
2. **Right-sizing + skippable review:** a small sprint plans with minimal sections and a recorded `architecture_review: skipped`, and still reaches `ticketed`/`executing`; a substantial sprint can still record a full review.
3. **No accumulation:** closing a sprint does not write into `docs/architecture/`; `docs/architecture/` is gone.
4. **On-demand consolidation:** running consolidate-architecture reads sprint docs + code and writes `docs/design/architecture.md`.
5. **Pre-close:** `review_sprint_pre_close` passes with only `sprint.md` finalized (no usecases/architecture draft checks). Full suite green; historical closed sprints still validate/render.

## Related

`clasi/issues/e2e-001-review.md` (#1 lightweight planning, #8 incremental/in-place architecture) — this change implements both. `clasi/issues/test-system-improvements-...md` — separate test-system/coverage work.
