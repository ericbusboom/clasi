---
name: architecture-authoring
description: Design and write architecture documents — initial architecture or sprint updates
---

# Architecture Authoring Skill

This skill guides writing architecture documents, whether an initial
architecture from scratch or a sprint update.

## Two Modes

### Mode 1: Initial Architecture

Design the system architecture from scratch when no architecture document
exists yet.

Given `.clasi/design/overview.md` and `.clasi/design/usecases.md`, produce
the first architecture document following steps 1-7 below.

### Mode 2: Sprint Architecture Update

Write the Architecture section of the sprint's `sprint.md`, sized to the
change — or write "N/A — trivial" when the change has no architectural
impact. This section is authored after the effort decision is made and
use cases are defined, and **before tickets exist** — tickets are derived
from it, not the other way around. The guiding question throughout is:
"Is this description clear enough that tickets can be derived from it
without ambiguity?"

Make an explicit sizing decision first, using three tiers, not two:

- **Trivial / small** — a bug fix, config tweak, or change confined to
  one module with no new component or data-model impact: minimal or
  omitted Architecture section (may read "N/A — trivial").
- **Compact** — one new or changed module/component, with *no* new
  cross-module dependency, *no* dependency-direction change, and *no*
  data-model change: full section structure (What Changed, Why, Impact,
  Migration Concerns) but no diagrams (see Step 4) and prose sized to
  describing one module — typically 300-500 words as a consequence of
  scope, not a target. This tier exists because "adds one module" is not
  the same problem as "introduces a subsystem," and treating it as such
  is what produces bloated plans for small projects.
- **Substantial / structural** — 3+ modules touched, a new/changed
  cross-module dependency, a dependency-direction change, or a data-model
  change: the full write-up below, diagrams included.

Judge the tier by concrete signals (module count, dependency changes,
data-model changes), not by guessing a word count first and writing to
it — a heuristic that misjudges a genuinely complex sprint as compact is
worse than one that occasionally treats a simple sprint as substantial.
When borderline, prefer the heavier tier and say why in the sizing
sentence.

At authoring time the section is a structural plan; after the sprint
closes it accumulates as a historical record (an ADR at sprint
granularity, embedded in that sprint's `sprint.md`). It is not merged
back into the canonical architecture docs — it stands on its own. See
the `consolidate-architecture` skill for how these per-sprint sections
are later merged into a consolidated architecture document, if needed.

Given the sprint plan and current architecture, write the Architecture
section with: Planned Changes, Rationale, Impact on Existing Components,
Migration Concerns.

### Revising in place

When an exception loop triggers an architecture revision, revise the
Architecture section of `sprint.md` **in place** — edit the section
directly rather than creating a separate revision file. Add a brief
`## Revision` note (or update the section's Design Rationale) describing
what changed and why, so the revision is visible without relying on file
history.

This supersedes the older convention (used by sprints planned before
sprint 018's single-doc rewrite) of writing separate
`architecture-update-r1.md`, `-r2.md`, etc. files that preserved the
original `architecture-update.md` untouched. Sprints planned under the
old three-document model may still have those files on disk as a
historical record — that is expected for sprints 001-017 and is not a
defect. New sprints revise the `sprint.md` Architecture section in place.

The team-lead and sprint-planner both reference this convention. The full
rule lives here; the sprint-planner agent carries only a brief
cross-reference.

## Steps

### 1. Understand the Problem
Read the overview, use cases, and (if updating) current architecture and
sprint plan.

### 2. Identify Responsibilities
List distinct responsibilities the system handles. Group related ones.
Separate those that change independently.

### 3. Define Subsystems and Modules
Map responsibility groups to modules. For each:
- **Purpose**: One sentence, no "and"
- **Boundary**: What is inside and outside
- **Use cases served**

### 4. Produce Diagrams
For **Mode 1 (Initial Architecture)** or a **substantial/structural**
sprint update, include:
1. **Component/Module Diagram** — subsystems as boxes, labeled edges.
   Required whenever 3+ modules are touched or a new cross-module
   dependency is introduced. If a substantial-tier sprint touches many
   existing modules for independent changes with no new composition
   between them, a diagram may be omitted — but state in one sentence why
   it wouldn't clarify anything (sprint 020 is a worked example: 9
   largely independent bugfix issues, no new subsystem, diagram omitted
   with a stated reason). Default to including it; the omission requires
   an articulated reason, not silence.
2. **Entity-Relationship Diagram** — entities, attributes, cardinality.
   Only if the data model changes.
3. **Dependency Graph** — module dependencies with labeled edges. Only if
   module dependencies change.

Guidelines: 5-12 nodes, label every edge, one concern per diagram.

For a **compact** sprint update (one new/changed module, no new
cross-module dependency, no data-model change), omit all diagrams. The
one-sentence purpose and boundary from Step 3 already say everything a
diagram would show for a single module.

### 5. Complete the Document
Sections: Architecture Overview, Technology Stack, Module Design, Data
Model, Dependency Graph, Security Considerations, Design Rationale, Open
Questions, Sprint Changes.

Stay at module/subsystem level. No function signatures or column schemas.

### 6. Document Design Rationale
For significant decisions: Decision, Context, Alternatives, Why this
choice, Consequences.

### 7. Flag Open Questions
List anything ambiguous or requiring stakeholder input.

## Quality Checks

- Every module addresses at least one use case
- Every use case addressed by at least one module
- Each module passes cohesion test (one sentence, no "and")
- Dependency graph has no cycles
- Fan-out no greater than 4-5 without justification
- Mermaid diagrams included for Mode 1 and substantial-tier sprint
  updates, unless omitted with a stated one-sentence reason; omitted by
  rule (no justification needed) for compact-tier sprint updates
- Document stays at module level
- For a compact-tier sprint update: no diagrams present, and length is
  proportionate to one module (roughly 300-500 words is typical, not a
  hard limit) — if the section runs much longer than that, check whether
  the sizing decision undercounted scope (a 3rd module, a new dependency,
  a data-model change) rather than trimming prose to fit
