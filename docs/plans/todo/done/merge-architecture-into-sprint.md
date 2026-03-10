---
title: Merge Architecture Document and Technical Plan into a Single Sprint Artifact
priority: high
supersedes: add-versioned-architecture-process/
---

# Merge Architecture Document and Technical Plan into a Single Sprint Artifact

## Problem

Agents consistently forget to update the architecture document because it
lives at the project level (`docs/plans/architecture/`) — outside the sprint
directory they're working in. The technical plan and architecture document
are also redundant: the technical plan describes "what changes we're making
to the architecture," and the architecture document describes "what the
architecture looks like after those changes." These are two views of the
same thing.

See: `docs/plans/reflections/2026-03-10-missing-architecture-update-in-sprint-summary.md`

## Proposal

Eliminate `technical-plan.md` as a separate artifact. Merge its content into
the architecture document, which becomes a first-class sprint artifact
(`architecture.md` inside the sprint directory).

### How It Works

**On `create_sprint`:**

1. Find the most recent architecture document — look for the top-level file
   in `docs/plans/architecture/` (the most recent version). Fall back to
   checking the most recently closed sprint's archived copy.
2. Copy it into the new sprint directory as `architecture.md`.
3. If no previous architecture document exists, create one from a template.

**During sprint planning (architect agent):**

1. Update the sprint's `architecture.md` to reflect the target end-of-sprint
   state — same as today, but in-place in the sprint directory.
2. Add/update a `## Sprint Changes` section at the bottom. Before execution
   this reads "Changes planned in this sprint" with a summary of intended
   modifications. This replaces the old technical-plan content (component
   design, architecture overview of changes, open questions).
3. For sprints with no architectural changes, copy the doc unchanged and write
   "No architectural changes in this sprint" in the Sprint Changes section.

**On sprint close:**

1. The architecture document gets archived with the rest of the sprint in
   `docs/plans/sprints/done/NNN-slug/`.
2. Copy the sprint's `architecture.md` to
   `docs/plans/architecture/architecture-NNN.md` where NNN is the sprint
   number. This is the long-term architecture history.
3. Move all previous architecture versions to `docs/plans/architecture/done/`.
   Only the most recent version lives at the top level.

**Architecture directory layout:**

```
docs/plans/architecture/
  architecture-027.md          # Most recent (from sprint 027)
  done/
    architecture-001.md        # Historical versions
    architecture-015.md
    architecture-026.md
```

**Source of truth:** During a sprint, the sprint-local `architecture.md` is
authoritative. Between sprints, the top-level file in
`docs/plans/architecture/` is authoritative (always the most recent).

## What Changes

### Files to Modify

1. **`claude_agent_skills/templates/`**
   - Delete `sprint-technical-plan.md` template.
   - Create `sprint-architecture.md` template (architecture document with
     a `## Sprint Changes` section at the bottom).

2. **`claude_agent_skills/templates.py`**
   - Remove `SPRINT_TECHNICAL_PLAN_TEMPLATE`.
   - Add `SPRINT_ARCHITECTURE_TEMPLATE`.

3. **`claude_agent_skills/artifact_tools.py`**
   - `create_sprint()`: Instead of creating `technical-plan.md`, copy the
     previous sprint's `architecture.md` into the new sprint directory.
     If no previous exists, use the template. Remove `technical-plan.md`
     from the created files list.
   - `insert_sprint()`: Same changes as `create_sprint()`.
   - Sprint review tools: Replace `technical-plan.md` checks with
     `architecture.md` checks.
   - `_is_template_placeholder()` calls: Update template references.

4. **`claude_agent_skills/skills/plan-sprint.md`**
   - Step 3 output list: Replace `technical-plan.md` with `architecture.md`.
   - Step 3/5/6: Reference `architecture.md` instead of `technical-plan.md`.
   - Add explicit instruction: "The architect updates the sprint's
     `architecture.md` to reflect the target state and fills in the Sprint
     Changes section."

5. **`claude_agent_skills/skills/create-technical-plan.md`**
   - Delete this skill. Mine it for useful guidance on how the architect
     should approach updates, fold that into a new `update-architecture`
     skill or into `plan-sprint`'s architecture step.

5b. **`claude_agent_skills/skills/close-sprint.md`** (if it exists)
   - Add step: copy sprint's `architecture.md` to
     `docs/plans/architecture/architecture-NNN.md`.
   - Add step: move previous architecture versions to
     `docs/plans/architecture/done/`.

6. **`claude_agent_skills/init/agents-section.md`** and **`AGENTS.md`**
   - Sprint lifecycle step 3: Replace "Fill in `sprint.md`, `usecases.md`,
     and `technical-plan.md`" with "Fill in `sprint.md`, `usecases.md`, and
     update `architecture.md`."

7. **`claude_agent_skills/instructions/architectural-quality.md`**
   - Rewrite "Architecture as a Living Document" section to describe the
     new sprint-local workflow: architecture lives in the sprint directory
     during the sprint, gets copied to `docs/plans/architecture/` on close.
   - Update versioning rules: the architecture version number IS the sprint
     number. `architecture-027.md` = architecture after sprint 027.
   - Describe the `docs/plans/architecture/done/` convention for history.
   - Keep all the quality principles, document structure, dependency
     analysis, etc. — those are unchanged.
   - Add guidance for the `## Sprint Changes` section.

8. **`claude_agent_skills/agents/architect.md`** (TODO draft exists)
   - Update "Your Artifacts" to describe the single `architecture.md` in
     the sprint directory instead of two separate artifacts.
   - Update "Mode 2: Sprint Architecture Update" to describe in-place
     editing of the sprint's `architecture.md`.

9. **`claude_agent_skills/agents/architecture-reviewer.md`** (TODO draft exists)
   - Update to review the sprint's `architecture.md` instead of looking
     in `docs/plans/architecture/`.

10. **Tests**
    - `tests/system/test_sprint_review.py`: Update all references from
      `technical-plan.md` to `architecture.md`.
    - `tests/unit/test_mcp_server.py`: Update if tool signatures change.
    - `tests/unit/test_init_command.py`: Update expected wording.
    - Add test: `create_sprint` copies previous architecture doc.
    - Add test: `create_sprint` uses template when no previous exists.

### Files to Delete

- `claude_agent_skills/templates/sprint-technical-plan.md` (replaced by
  `sprint-architecture.md`)
- `claude_agent_skills/skills/create-technical-plan.md` (absorbed into
  architecture workflow)

### Existing TODO to Supersede

The `docs/plans/todo/add-versioned-architecture-process/` directory contains
draft replacements for the architect agent, architecture-reviewer agent, and
architectural-quality instruction. Those drafts assume the old two-artifact
model (separate architecture doc + technical plan). This TODO supersedes
that entire directory — move it to `docs/plans/todo/done/` when this work
begins.

## What Does NOT Change

- `sprint.md` — still exists, still tracks goals/scope/ticket list
- `usecases.md` — still exists, still tracks sprint use cases
- `brief.md` — still exists at sprint level
- Sprint phases and gates — same lifecycle
- Architecture quality principles — same criteria
- Ticket creation from the plan — tickets are now derived from the Sprint
  Changes section of `architecture.md`

## Architecture Document Structure (New)

The sprint's `architecture.md` follows the same structure as before:

1. Architecture Overview (with Mermaid diagrams)
2. Technology Stack
3. Component Design
4. Dependency Map
5. Data Model
6. API Design
7. Security Considerations
8. Design Rationale
9. Open Questions
10. **Sprint Changes** ← NEW, replaces technical-plan.md

The Sprint Changes section contains:
- Summary of what's being added/modified/removed
- Component-level detail for changed components (what the old technical
  plan's "Component Design" section covered)
- Migration concerns if any

## Resolved Questions

1. **Architecture snapshots on close**: Yes, mandatory. On sprint close,
   copy the sprint's `architecture.md` to
   `docs/plans/architecture/architecture-NNN.md` (NNN = sprint number).
   Move previous versions to `docs/plans/architecture/done/`. The
   architecture directory keeps the version numbering scheme — it's the
   long-term history. The sprint number IS the architecture version number.

2. **`create-technical-plan` skill**: Delete it. There is no longer a
   "technical plan" artifact. Mine it for insights on how the architect
   should work, then fold relevant guidance into a new
   `update-architecture` skill or into the `plan-sprint` skill's
   architecture step.
