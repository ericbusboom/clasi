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

Make an explicit sizing decision first: trivial/small changes get a
minimal or omitted Architecture section (may read "N/A — trivial");
substantial/structural changes get the full write-up below.

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
Required Mermaid diagrams:
1. **Component/Module Diagram** — subsystems as boxes, labeled edges
2. **Entity-Relationship Diagram** — entities, attributes, cardinality
3. **Dependency Graph** — module dependencies with labeled edges

Guidelines: 5-12 nodes, label every edge, one concern per diagram.

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
- Mermaid diagrams included
- Document stays at module level
