---
status: done
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016 Use Cases

These use cases cover the user-visible surface of this sprint. Each describes
a concrete developer or agent scenario using Given/When/Then.

The architecture-update is a free-prose planning document. It is authored at
the front of sprint planning, before tickets exist, and accumulates as a
historical record (ADRs at sprint granularity) when the sprint closes. It does
NOT merge into source-of-truth docs. Canonical design docs are project-init
artifacts, frozen after initiation.

**Scope note**: Sprint 016 scope has been narrowed based on verification reads.
The phase machine, sprint-planner agent, and architecture-review skill are
already correct. Only `architecture-authoring/SKILL.md` (Mode 2 framing) and
external documentation need changes. SUC-001 and SUC-002 remain; SUC-003 and
SUC-004 are removed (they covered correctness that already exists in code).

---

## SUC-001: Architecture-authoring skill guides writing a forward-looking plan

**Actor**: Sprint-planner agent invoking the `architecture-authoring` skill

**Context**: The sprint-planner is in Phase 2 — it has written `sprint.md` and
`usecases.md` and is about to write `architecture-update.md`. It invokes the
`architecture-authoring` skill for guidance.

- **Given**: The `architecture-authoring/SKILL.md` Mode 2 description exists.

- **When**: The sprint-planner reads the Mode 2 description to understand what
  to produce.

- **Then**: The description frames the artifact as a *forward-looking* structural
  plan — "describe the architectural change clearly enough that tickets can be
  derived from it." The planner understands that this document is authored
  before tickets exist and that tickets will be derived from it.

**Acceptance Criteria**:
- [ ] `architecture-authoring/SKILL.md` Mode 2 opening does NOT use the phrase
  "what changed" or any retrospective framing.
- [ ] Mode 2 explicitly states the artifact is authored before tickets exist.
- [ ] Mode 2 states the guiding question: "Is this description clear enough
  that tickets can be derived from it without ambiguity?"
- [ ] No reference to a parser, validator, delta format, or CLI subcommand.
- [ ] The artifact name remains `architecture-update.md` (not renamed).

---

## SUC-002: Documentation correctly describes the architecture-update model

**Actor**: Developer or agent reading the SE process documentation

**Context**: A developer or new agent reads `software-engineering.md`,
`se-overview-template.md`, or `README.md` to understand how
`architecture-update.md` works in the CLASI process.

- **Given**: The documentation files describe the sprint planning process and
  the role of `architecture-update.md`.

- **When**: The reader wants to understand: when is the file authored, what
  purpose does it serve, and does it get merged anywhere?

- **Then**: The documentation states clearly:
  - `architecture-update.md` is authored at the front of sprint planning, before
    tickets are created.
  - Per-sprint files accumulate as ADRs at sprint granularity. When the sprint
    closes, the file travels intact to `done/<id>/` — a historical record.
  - Canonical design docs are project-init artifacts, frozen after initiation.
    Sprint close does NOT modify them.
  - "What is the current architecture?" is answered by reading the code. The
    per-sprint updates are the chronological record of structural intent.

**Acceptance Criteria**:
- [ ] `software-engineering.md` Architecture artifact section does NOT say
  "each version represents the target state after a sprint completes" in
  a way that implies a merge/consolidation step for `architecture-update.md`.
- [ ] `software-engineering.md` correctly describes per-sprint
  `architecture-update.md` as a planning-time artifact accumulated as
  historical record.
- [ ] `se-overview-template.md` includes at least one sentence about
  `architecture-update.md` being authored before tickets at sprint planning.
- [ ] `README.md` sprint planning description is consistent with the above.
- [ ] No documentation file states `architecture-update.md` is written at
  sprint close or as a retrospective record.
