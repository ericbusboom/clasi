---
sprint: "017"
status: draft
---

# Use Cases — Sprint 017: Two-phase sprint planning: roadmap then detail

## SUC-001: Lightweight sprint creation (roadmap only)

**As a** team-lead or sprint-planner agent,
**I want to** call `create_sprint(title=...)` and receive a sprint with only
`sprint.md` written (status: roadmap),
**so that** I can plan many sprints in batch without committing to full
artifact scaffolding upfront.

**Acceptance criteria:**
- `create_sprint` writes exactly one file: `sprint.md` with `status: roadmap` in frontmatter.
- No `usecases.md`, no `architecture-update.md`, no `tickets/` directory created.
- The sprint is registered in the state DB at phase `roadmap`.
- Calling `get_sprint_phase` on the new sprint returns `{"phase": "roadmap"}`.

---

## SUC-002: Roadmap sprint promotion to detail planning

**As a** sprint-planner agent beginning detail work on a previously roadmapped sprint,
**I want to** call `detail_sprint(sprint_id)` and have the full artifact set
scaffolded for me,
**so that** I can proceed directly to writing use cases and architecture without
manually creating directories and template files.

**Acceptance criteria:**
- `detail_sprint` validates the sprint is in `roadmap` phase; returns a clear
  error if it is already in a later phase.
- On success, writes `usecases.md`, `architecture-update.md`, `tickets/`, and
  `tickets/done/` using the existing templates.
- The state DB phase advances from `roadmap` to `planning-docs`.
- Calling `detail_sprint` a second time on the same sprint returns an error
  (no silent partial re-scaffold).

---

## SUC-003: List sprints filtered by roadmap status

**As a** team-lead reviewing the sprint queue,
**I want to** call `list_sprints(status="roadmap")` and see only roadmap sprints,
**so that** I can distinguish planning-ready sprints from detail-planned or
executing sprints.

**Acceptance criteria:**
- `list_sprints(status="roadmap")` returns only sprints whose `sprint.md`
  has `status: roadmap`.
- Default `list_sprints()` (no status argument) returns all sprints regardless
  of status.
- Sprints in `planning-docs`, `ticketing`, `executing`, or `done` do not appear
  in the roadmap filter result.

---

## SUC-004: State machine enforces roadmap-first sequencing

**As a** process author,
**I want** the state machine to place `roadmap` as the first phase,
**so that** a roadmap sprint cannot skip directly to `architecture-review` or
later without going through `detail_sprint` first.

**Acceptance criteria:**
- `PHASES` constant in `state_db_class.py` begins with `roadmap`.
- Attempting to advance a `roadmap` sprint to `architecture-review` directly
  (without calling `detail_sprint`) is rejected by the state machine.
- `detail_sprint` is the only sanctioned path from `roadmap` to `planning-docs`.
- Phase transitions from `planning-docs` onward are unchanged.

---

## SUC-005: Skill and agent prose reflects actual tool-level two-phase flow

**As a** sprint-planner agent reading the skill documentation,
**I want** the `plan-sprint` skill, `sprint-planner` agent, `sprint-roadmap`
skill, and `team-lead` agent to describe exactly which MCP tools are called
in each phase,
**so that** I do not need workarounds and the documentation does not contradict
the tool implementation.

**Acceptance criteria:**
- `sprint-roadmap` SKILL.md no longer contains workaround steps for deleting
  extra artifacts; it describes calling the lightweight `create_sprint` directly.
- `plan-sprint` SKILL.md Phase 1 describes `create_sprint` producing only
  `sprint.md`; Phase 2 describes calling `detail_sprint` before writing
  planning artifacts.
- `sprint-planner` agent.md tightens Roadmap Mode and Detail Mode descriptions
  to match the actual MCP tool sequence.
- `team-lead` agent.md distinguishes roadmap sprints (not yet detail-planned)
  from planning-docs sprints (ready for execution dispatch).
- No contradictions between documented model and the enforced phase machine.

---

## SUC-006: Tests cover new lifecycle transitions

**As a** developer maintaining CLASI,
**I want** a test suite that covers the roadmap → detail lifecycle,
**so that** regressions in `create_sprint`, `detail_sprint`, or `PHASES` are
caught before release.

**Acceptance criteria:**
- Unit tests verify `create_sprint` produces only `sprint.md`.
- Unit tests verify `detail_sprint` scaffolds the full artifact set and
  advances phase from `roadmap` to `planning-docs`.
- Unit tests verify `detail_sprint` rejects sprints not in `roadmap` phase.
- Unit tests verify `roadmap` is the first entry in `PHASES`.
- System tests verify the MCP tool registration and a round-trip lifecycle:
  `create_sprint` → `list_sprints(status="roadmap")` → `detail_sprint` →
  `get_sprint_phase` returns `planning-docs`.
- Existing test suite stays green.
