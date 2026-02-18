---
status: done
sprint: '014'
---

# Add Versioned Architecture Process

Introduce versioned architecture documents, upgrade the architect and
architecture-reviewer agents, and add an architectural quality guide.
This replaces the current flat technical-plan-only approach with a
living architecture that evolves sprint by sprint.

## Reference Files

The new agent definitions and quality guide are stored alongside this
todo in `docs/plans/todo/add-versioned-architecture-process/`:

- `architect.md` — Replacement for `claude_agent_skills/agents/architect.md`
- `architecture-reviewer.md` — Replacement for `claude_agent_skills/agents/architecture-reviewer.md`
- `architectural-quality.md` — New file for `claude_agent_skills/instructions/architectural-quality.md`

## What Changes

### 1. Create the architecture directory and initial document

Create `docs/plans/architecture/` as a new directory. Produce
`architecture-001.md` representing the current system state (before any
architecture-aware sprint runs). This is a retroactive baseline — it
describes the system as it exists today.

The architect agent's "Mode 1: Initial Architecture" (see `architect.md`
Step 1–7) drives this. Inputs are the existing `docs/plans/overview.md`
(or legacy brief/usecases) plus the current codebase.

### 2. Replace the architect agent

Replace `claude_agent_skills/agents/architect.md` with the new version
from the reference files. Key differences from the current agent:

- **Current**: Produces a single flat `technical-plan.md` from brief +
  use cases. No versioning, no sprint-awareness.
- **New**: Produces versioned `architecture-NNN.md` documents plus sprint
  technical plans. Two modes of work: initial architecture (Stage 1b) and
  sprint architecture update. Seven-step process (understand, identify
  responsibilities, define components/boundaries, map dependencies,
  complete document, document rationale, flag open questions).

The new agent references `instructions/architectural-quality.md` for
document structure, cohesion/coupling criteria, interface specs, and
anti-patterns.

### 3. Replace the architecture-reviewer agent

Replace `claude_agent_skills/agents/architecture-reviewer.md` with the
new version. Key differences:

- **Current**: Lightweight review of sprint plans against codebase and
  technical plan. Simple APPROVE / APPROVE WITH CHANGES / REVISE verdicts.
- **New**: Reviews both the proposed architecture version AND the sprint
  technical plan. Six review criteria: version consistency, codebase
  alignment, design quality (cohesion/coupling/boundaries/dependencies/
  abstraction), anti-pattern detection, risks, missing considerations,
  design rationale. Adds "Design Quality Assessment" section to every
  review. Detailed verdict guidelines (e.g., circular dependencies →
  REVISE, missing rationale → APPROVE WITH CHANGES).

### 4. Add the architectural quality guide

Install `architectural-quality.md` as a new instruction file at
`claude_agent_skills/instructions/architectural-quality.md`. This is
the shared reference for both the architect and architecture-reviewer.

Contents: versioning rules, core principles (cohesion, coupling,
boundary definition, appropriate abstraction, dependency direction),
architecture document structure, dependency mapping format, interface
specification format, design rationale format, anti-patterns to flag.

### 5. Update the sprint lifecycle in software-engineering.md

The sprint lifecycle currently goes:

```
planning-docs → architecture-review → stakeholder-review → ticketing → executing → closing → done
```

The `planning-docs` phase needs to be updated to include architecture
work. The new flow within sprint planning is:

1. Write `sprint.md` — describe the sprint goals, problem, solution
2. Write `usecases.md` — sprint-level use cases
3. **Architect produces new architecture version** — starting from the
   current `architecture-NNN.md`, produce `architecture-(N+1).md`
   describing the target state after the sprint completes. This happens
   during the `planning-docs` phase.
4. **Architect produces sprint `technical-plan.md`** — describes the
   delta from version N to N+1. States "from version" and "to version",
   lists changes to components/interfaces/dependencies/data model,
   rationale referencing sprint goals, and migration concerns.
5. **Architecture reviewer reviews** (existing `architecture-review`
   phase) — now reviews both the new architecture version AND the
   technical plan against the quality guide.
6. Stakeholder review (unchanged)
7. Ticketing — tickets derived from the technical plan's delta
8. Implementation (unchanged)

The `software-engineering.md` needs to:
- Reference the architecture directory in the directory layout
- Update the sprint lifecycle description to include architecture
  versioning
- Update the architect agent description to reflect versioned output
- Update the architecture-reviewer description to reflect expanded review
- Reference `instructions/architectural-quality.md` in the agent list
- Note that not every sprint requires a new architecture version (pure
  bug-fix or refactor sprints within existing boundaries skip it)

### 6. Update the sprint directory structure

The sprint directory layout in `software-engineering.md` should
acknowledge that the technical plan now references architecture versions.
No structural change to the sprint directory itself, but the
`technical-plan.md` template should include "From version" / "To version"
fields.

### 7. Update sprint templates

If there are template files used to generate sprint directories (check
the MCP server's `create_sprint` tool implementation), update them to:
- Add architecture version reference fields to `technical-plan.md`
  template
- Possibly add a reminder in `sprint.md` template about architecture
  update

### 8. Harmonization notes

A few points where the new files need to align with the existing process:

- **Path references**: The new agents reference
  `instructions/architectural-quality.md` and
  `instructions/software-engineering.md`. Verify these resolve correctly
  within the agent/instruction loading system (the actual paths are
  `claude_agent_skills/instructions/...`).
- **Sprint technical plan vs. top-level technical plan**: The existing
  process has both a legacy top-level `docs/plans/technical-plan.md` and
  per-sprint `technical-plan.md` files. The new architect agent's Mode 2
  produces sprint-level technical plans. The top-level technical plan
  becomes a legacy artifact; the architecture document replaces it as the
  authoritative system description.
- **Architecture version numbering vs. sprint numbering**: Per the
  quality guide, these are independent. A sprint's technical plan
  references which architecture version it targets. Not every sprint
  bumps the architecture version.
- **The new architect references `docs/plans/brief.md` and
  `docs/plans/usecases.md`** as inputs for Mode 1. For projects using
  the newer `overview.md` approach, the agent instructions should note
  that `overview.md` serves as the input instead.
- **The new architecture-reviewer references the quality guide** at
  `instructions/architectural-quality.md`. This file doesn't exist yet —
  it needs to be created as part of this work (item 4 above).

## Process Ordering for Implementation

When this todo is consumed into a sprint, the implementation order is:

1. Install `architectural-quality.md` as an instruction file (no
   dependencies)
2. Replace the architect agent definition
3. Replace the architecture-reviewer agent definition
4. Update `software-engineering.md` to reference the new process
5. Update sprint templates if applicable
6. Produce the initial `architecture-001.md` baseline document
7. Verify the whole flow works by doing a dry-run sprint plan

Items 1–3 are file replacements. Item 4 is the main editing work.
Item 6 requires the architect agent to actually run against the current
codebase. Item 7 is validation.
