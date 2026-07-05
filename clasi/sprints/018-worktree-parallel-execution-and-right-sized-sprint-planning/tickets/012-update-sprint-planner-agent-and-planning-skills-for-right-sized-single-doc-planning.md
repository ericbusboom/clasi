---
id: '012'
title: Update sprint-planner agent and planning skills for right-sized single-doc
  planning
status: done
use-cases:
- SUC-004
depends-on:
- '002'
- '004'
- '005'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint-planner agent and planning skills for right-sized single-doc planning

## Description

Issue B Part 3. Depends on ticket 002 (templates already folded), ticket
004 (state machine + `skipped` gate result already exist), and ticket 005
(schema.yaml/`insert_sprint`/`review_sprint_pre_close` already updated)
so the process documentation describes the system's actual post-rewrite
behavior rather than a still-in-progress one.

Update the planning-agent and skill documentation to describe the
one-document model and explicit right-sizing guidance:

1. **`src/clasi/plugin/agents/sprint-planner/agent.md`** — the agent
   definition this very sprint-planner agent operates under. Update its
   workflow description to: author ONE `sprint.md` with Architecture +
   Use Cases as right-sized sections (not separate `usecases.md`/
   `architecture-update.md`); make an explicit effort decision by
   feature size (trivial/small: minimal or omitted sections, skip
   architecture review, record `skipped`; substantial/structural: full
   sections + full review, matching the 7-step methodology this very
   ticket's own sprint used as a worked example). This is the same file
   whose current contents I (the sprint-planner) am operating under for
   THIS sprint 018 — note in the ticket completion that this sprint
   itself was planned before this rewrite landed (chicken-and-egg,
   expected and fine — sprint 018 correctly used the pre-rewrite
   three-document model since Issue B had not shipped yet when this
   sprint was planned).
2. **`src/clasi/plugin/agents/sprint-planner/plan-sprint.md`** — update
   references to `usecases.md`/`architecture-update.md` scaffolding to
   match ticket 003's `detail_promote()` behavior (scaffolds only
   `tickets/`+`tickets/done/`).
3. **`src/clasi/plugin/agents/sprint-planner/dispatch-template.md.j2`** —
   update any references to the two separate files in the dispatch
   context template.
4. **`src/clasi/plugin/agents/sprint-planner/contract.yaml`** — update
   the `outputs.detail.required` list (currently includes `usecases.md`
   and `architecture-update.md` as separate required paths) to reflect
   `sprint.md` with required Architecture/Use Cases content instead;
   update `architecture_review` enum values in `returns.detail` if needed
   to include `skipped` explicitly (currently `[passed, failed, skipped]`
   — check if `skipped` is already there; if so no change needed for that
   enum, only for the `outputs` file list).
5. **`architecture-authoring` skill**
   (`src/clasi/plugin/skills/architecture-authoring/SKILL.md`)  —
   reframe "Mode 2: Sprint Architecture Update" to "write the
   architecture *section* of sprint.md, sized to the change, or write
   'N/A — trivial'"; drop the `architecture-update-rN.md` separate-file
   revision convention (revise the section in place within `sprint.md`
   instead — remove the "Revision naming and preservation" subsection or
   rewrite it to describe in-place section revision).
6. **`architecture-review` skill**
   (`src/clasi/plugin/skills/architecture-review/SKILL.md`) — update to
   describe reviewing the sprint.md architecture section, and state
   explicitly that the review is skippable for small sprints (record
   `skipped`).
7. **`create-tickets` skill**
   (`src/clasi/plugin/skills/create-tickets/SKILL.md` AND
   `src/clasi/plugin/agents/sprint-planner/create-tickets.md`, which is a
   near-duplicate — check both) — change "Inputs" from
   `architecture-update.md` + `usecases.md` to `sprint.md` (its
   Architecture + Use Cases sections).
8. Update cross-references in `software-engineering.md`,
   `subagent-protocol.md`, `team-lead/agent.md`, `programmer/agent.md`,
   `project-status.md`, and the schema instructions (`sprint-plan.md`,
   `architecture-update.md`) — grep for `usecases.md` and
   `architecture-update.md` across `src/clasi/plugin/` and
   `src/clasi/schemas/` to find the full set of cross-references; this
   list from the issue is representative, not exhaustive — the grep is
   the actual source of truth for what needs updating.

This ticket is documentation/process-guidance only — it does not change
any Python code, MCP tool, or test-covered behavior beyond what tickets
002-005 already implemented. Its "testing" is closer to a
consistency/grep check than behavioral test coverage.

## Acceptance Criteria

- [x] `sprint-planner/agent.md` describes the one-`sprint.md` model with
      right-sized Architecture/Use Cases sections and an explicit
      size-based effort decision (trivial/small vs. substantial/
      structural), matching this ticket's own worked example (sprint 018
      itself, planned under the old model, is the one exception noted).
- [x] `sprint-planner/plan-sprint.md`,
      `sprint-planner/dispatch-template.md.j2`, and
      `sprint-planner/contract.yaml` no longer reference
      `usecases.md`/`architecture-update.md` as separate required
      outputs.
- [x] `architecture-authoring/SKILL.md`'s Mode 2 describes revising the
      sprint.md Architecture section in place; the `-rN.md` separate-file
      revision convention is removed or explicitly superseded.
- [x] `architecture-review/SKILL.md` states the review is skippable for
      small sprints.
- [x] Both `create-tickets` skill files describe `sprint.md` as the input
      instead of the two separate files.
- [x] A repo-wide grep for `usecases.md` and `architecture-update.md`
      within `src/clasi/plugin/` and `src/clasi/schemas/se-process/`
      after this ticket's edits shows no remaining references describing
      them as required/mandatory sprint-planner outputs (references
      describing historical/backward-compat behavior for sprints 001-017
      are fine and should remain).

## Files to create or modify

- `src/clasi/plugin/agents/sprint-planner/agent.md`
- `src/clasi/plugin/agents/sprint-planner/plan-sprint.md`
- `src/clasi/plugin/agents/sprint-planner/dispatch-template.md.j2`
- `src/clasi/plugin/agents/sprint-planner/contract.yaml`
- `src/clasi/plugin/agents/sprint-planner/create-tickets.md`
- `src/clasi/plugin/skills/architecture-authoring/SKILL.md`
- `src/clasi/plugin/skills/architecture-review/SKILL.md`
- `src/clasi/plugin/skills/create-tickets/SKILL.md`
- `src/clasi/plugin/skills/plan-sprint/SKILL.md` (if it references the
  two files directly)
- Cross-referencing docs found via grep: likely candidates include
  `software-engineering.md`, `subagent-protocol.md`,
  `team-lead/agent.md`, `programmer/agent.md`, `project-status.md`,
  `se-process/instructions/sprint-plan.md`,
  `se-process/instructions/architecture-update.md` — confirm exact paths
  via grep before editing, do not assume a path exists without checking.

## Testing

- **Existing tests to run**: any test asserting on agent/skill file
  content (grep `tests/` for references to these file paths or their
  content), full `uv run pytest`.
- **New tests to write**: none expected (documentation-only change); if
  the repo has content-consistency tests for agent/skill files, extend
  them, otherwise skip.
- **Verification command**: `uv run pytest` plus a manual
  `grep -rn "usecases.md\|architecture-update.md" src/clasi/plugin/
  src/clasi/schemas/se-process/` review confirming only expected
  historical/backward-compat references remain.

## Completion Notes

Documentation/process-guidance sweep only -- no Python code changed.

**Files updated** (single-doc model description):
- `src/clasi/plugin/agents/sprint-planner/agent.md` -- Role, What You
  Return, Planning Modes, added an "Effort Decision" section, rewrote the
  Detail Mode Workflow phases (scaffolding, Use Cases, Architecture,
  self-review skip path), Rules, and Exception Protocol surface
  classification.
- `src/clasi/plugin/agents/sprint-planner/plan-sprint.md` -- Phase 2
  description, Detail Process steps (effort decision inserted as its own
  step, architecture review step made conditionally skippable, renumbered
  subsequent steps), Detail Output.
- `src/clasi/plugin/agents/sprint-planner/dispatch-template.md.j2` --
  roadmap/detail "what to produce" lists, `files_created` JSON examples,
  behavioral instructions.
- `src/clasi/plugin/agents/sprint-planner/contract.yaml` -- removed
  `usecases.md`/`architecture-update.md` as separate required output
  paths; added a `validates` note describing the right-sized sections
  living inside `sprint.md`. Confirmed `architecture_review` enum already
  included `skipped` (no change needed there).
- `src/clasi/plugin/agents/sprint-planner/create-tickets.md` -- Inputs
  section now points to `sprint.md`.
- `src/clasi/plugin/skills/architecture-authoring/SKILL.md` -- Mode 2
  reframed to sprint.md section authoring; "Revision naming and
  preservation" replaced with "Revising in place", explicitly superseding
  the old `-rN.md` convention for sprints planned after the rewrite while
  noting sprints 001-017 may still have the old files on disk.
- `src/clasi/plugin/skills/architecture-review/SKILL.md` -- added a
  "Skippable for Small Sprints" section.
- `src/clasi/plugin/skills/create-tickets/SKILL.md` -- Inputs section now
  points to `sprint.md`.
- `src/clasi/plugin/instructions/subagent-protocol.md`,
  `src/clasi/plugin/instructions/software-engineering.md` (Architecture
  §2, Sprints §4 directory diagram, Sprints workflow bullet, Directory
  Layout diagram), `src/clasi/plugin/agents/team-lead/agent.md`
  (dispatch description, exception-routing steps, Never-Write-Content
  rule), `src/clasi/plugin/agents/programmer/agent.md` (surface
  classification), `src/clasi/schemas/se-process/instructions/sprint-plan.md`,
  `src/clasi/schemas/se-process/instructions/architecture-update.md` --
  cross-reference updates found via the grep below.
- `src/clasi/plugin/skills/plan-sprint/SKILL.md` checked -- it only
  points to `sprint-plan.md` via "Load from:" and does not itself
  reference the two files, so no edit was needed there.

**Left unchanged (correctly out of scope)**: `.clasi/design/usecases.md`
and `.clasi/brief.md`/top-level `usecases.md` references throughout
(`project-initiation` skill, `project-status` skill and agent doc,
`software-engineering.md`'s "Legacy: Brief, Use Cases, Technical Plan"
section and Directory Layout top-level entry, `team-lead/agent.md`'s
Project Initiation step) -- these describe project-level use cases, a
distinct and still-valid concept from sprint-level use cases. Also left
unchanged: everything under `src/clasi/plugin/agents/old/` (architect,
architecture-reviewer, project-manager, technical-lead, sprint-executor,
code-reviewer) -- these are retired agents kept for historical reference,
not the current sprint-planner.

**Grep before** (repo-wide, `src/clasi/plugin/` + `src/clasi/schemas/se-process/`):
59 matches across sprint-planner files, cross-reference docs, `old/`
agents, and project-level docs.

**Grep after** the same two roots: remaining matches are exclusively (a)
explicit backward-compat notes I added (e.g. "Sprints planned before the
single-doc rewrite -- sprints 001-017 -- ..."), (b) `agents/old/*`
retired-agent files, and (c) `.clasi/design/usecases.md` /
top-level-legacy project-initiation references. No remaining reference
describes `usecases.md` or `architecture-update.md` as a current/required
sprint-planner output or input.

**Chicken-and-egg note**: This ticket updates the sprint-planner's own
`agent.md` and skills to describe the single-doc model, but sprint 018
itself (the sprint this ticket lives in) was planned under the *old*
three-document model -- it has its own separate `usecases.md` and
`architecture-update.md` files in
`clasi/sprints/018-worktree-parallel-execution-and-right-sized-sprint-planning/`.
This is correct and expected: sprint 018 was planned before Issue B
(this rewrite) shipped, so the sprint-planner that planned it was
operating under the pre-rewrite rules. `agent.md` now explicitly notes
this exception inline. Sprint 018's own planning artifacts were not
touched or "fixed" retroactively -- only tickets/012's own frontmatter
and this file were modified within the sprint directory.

**Verification**: `uv run pytest` -- 2425 passed, coverage 87.90%
(threshold 84%). No test asserted on the specific file paths removed from
`contract.yaml`'s `outputs.detail.required`; `test_contracts.py` and
`test_skill_stub_loader.py` (which check `architecture-review/SKILL.md`'s
"Load from:" directive) both still pass because the "Load from:" line was
preserved, only new prose was added above it.
