---
name: architectural-quality
description: Principles and criteria for evaluating architectural quality — referenced by the architect and architecture-reviewer agents
---

# Architectural Quality Guide

This guide defines the principles and criteria for evaluating architectural
quality. It is referenced by the **architect** (when designing and updating
the architecture) and the **architecture-reviewer** (when reviewing).

## Architecture as a Living Document

The architecture document is a **sprint-level artifact**. During each sprint,
it lives inside the sprint directory as `architecture.md`. This ensures the
architecture is visible to agents working on the sprint, not hidden in a
project-level directory.

### Lifecycle

1. **On sprint creation** — `create_sprint` copies the latest architecture
   version into the new sprint directory as `architecture.md`. If no previous
   version exists, a template is used.

2. **During sprint planning** — The architect updates the sprint's
   `architecture.md` to reflect the target end-of-sprint state and fills in
   the `## Sprint Changes` section describing what is being added, modified,
   or removed. For sprints with no architectural changes, the Sprint Changes
   section says "No architectural changes in this sprint."

3. **On sprint close** — The sprint's `architecture.md` is copied to
   `docs/clasi/architecture/architecture-NNN.md` where NNN is the sprint
   number. Previous versions are moved to `docs/clasi/architecture/done/`.

### Architecture Directory Layout

```
docs/clasi/architecture/
  architecture-027.md          # Most recent (from sprint 027)
  done/
    architecture-001.md        # Historical versions
    architecture-015.md
    architecture-026.md
```

Only the most recent version lives at the top level. The architecture version
number **is** the sprint number.

### What the Document Describes

The architecture document describes **what the system is** — its components,
boundaries, interfaces, dependencies, data model, and design rationale. It
is a specification of the system's structure, not a plan of work.

The `## Sprint Changes` section at the bottom describes **what changes are
being made** in the current sprint. Tickets are derived from this section.

### Source of Truth

- **During a sprint**: The sprint-local `architecture.md` is authoritative.
- **Between sprints**: The top-level file in `docs/clasi/architecture/` is
  authoritative (always the most recent version).

## Core Principles

### 1. Cohesion

A component is cohesive when everything inside it changes for the same
reasons and at the same rate. Test cohesion by asking:

- **Single Responsibility**: Can you describe what this component does in
  one sentence without using "and"?
- **Reason to Change**: If a requirement changes, does the change affect
  most of this component, or just a small corner of it? If the latter, the
  component likely bundles unrelated concerns.
- **Conceptual Unity**: Would a new developer understand why these pieces
  are together, or would they be surprised by what they find?

Poor cohesion shows up as components where a change to one feature forces
you to navigate past unrelated code, or where a component's name is vague
("utils", "helpers", "manager", "service" with no qualifier).

### 2. Coupling

Coupling is the degree to which one component depends on the internals of
another. The goal is not zero coupling (that would mean the system does
nothing) but *intentional, minimal, well-managed* coupling.

- **Depend on interfaces, not implementations.** A component should interact
  with another through a defined contract, not by reaching into its internals.
- **Dependency direction matters.** Dependencies should flow from unstable
  (frequently changing) components toward stable (rarely changing) ones.
  Business logic should not depend on infrastructure details.
- **No circular dependencies.** If A depends on B and B depends on A, they
  are effectively one component with a confusing boundary. Refactor by
  extracting the shared concern or inverting one dependency.
- **Minimize fan-out.** A component that depends on many others is fragile.
  If a component has more than 3-4 direct dependencies, consider whether
  it is doing too much or whether an intermediate abstraction is missing.

### 3. Boundary Definition

Good boundaries make a system understandable and changeable. A boundary is
well-defined when:

- **The interface is narrow.** The component exposes only what consumers
  need, nothing more. Internal data structures, helper functions, and
  implementation state are not visible.
- **The boundary is enforceable.** There is a mechanism (module structure,
  access control, API layer) that prevents consumers from bypassing the
  interface.
- **Cross-boundary communication uses explicit contracts.** Data passed
  across boundaries has a defined shape (schema, type, protocol). Components
  do not share mutable state.

### 4. Appropriate Abstraction

Abstraction levels should match the problem structure:

- **Don't over-abstract.** Abstractions that exist "in case we need them
  later" add complexity without value. Introduce abstractions when you have
  evidence of variation, not speculation.
- **Don't under-abstract.** When two components share a pattern and diverge
  only in details, a missing abstraction causes duplication and inconsistency.
- **Layer consistently.** If the system has layers (e.g., transport, business
  logic, persistence), every request should pass through the same layers in
  the same order. Shortcuts that skip layers create hidden coupling.

### 5. Dependency Direction

Organize components so that dependencies flow in one direction:

```
[Presentation / API] → [Business Logic / Domain] → [Infrastructure / Persistence]
```

- **Domain components should have no outward dependencies.** They define
  interfaces that infrastructure components implement.
- **Infrastructure is a plugin.** Databases, external APIs, file systems —
  these are implementation details that can be swapped without changing
  business logic.
- **Entry points orchestrate.** The API layer, CLI, or event handler
  assembles dependencies and calls into the domain. It is allowed to know
  about everything; nothing should know about it.

## Architecture Document Structure

Every architecture version should contain these sections:

1. **Architecture Overview** — High-level structure and the component/module
   diagram (Mermaid). This is the first thing a reader sees.
2. **Technology Stack** — Languages, frameworks, databases, infrastructure,
   with justifications against the brief's constraints.
3. **Module Design** — Each module or subsystem with:
   - Purpose (one sentence, no "and")
   - Boundary (what is inside, what is outside)
   - Key interactions with other modules
   - Use cases served
4. **Data Model** — Entity-relationship diagram (Mermaid `erDiagram`) showing
   entities, relationships, and cardinality. Brief prose descriptions of
   key entities. Do NOT list column schemas — the ERD communicates structure;
   column-level detail belongs in code or sprint-level plans.
5. **Dependency Graph** — Mermaid diagram of module dependencies with labeled
   edges. Accompanied by analysis of cycles, fan-out, and stability.
6. **Security Considerations** — Authentication, authorization, data
   protection.
7. **Design Rationale** — Significant decisions with alternatives and
   reasoning (see below).
8. **Open Questions** — Anything ambiguous, assumed, or requiring
   stakeholder input.
9. **Sprint Changes** — Summary of changes planned or made in this sprint.
   Component-level detail for changed components. Migration concerns.
   This section describes the delta from the previous architecture version.

### Level of Detail

The architecture document operates at the **module and subsystem level**.
It describes what exists, why it exists, and how parts relate.

**Include**: Module purposes, boundaries, responsibilities, entity
relationships, dependency direction, design trade-offs.

**Exclude**: Function signatures, method lists, parameter types, database
column schemas, internal algorithms. These belong in code, docstrings, or
the Sprint Changes section or ticket plans.

### Required Mermaid Diagrams

Every architecture version must include at minimum:

1. **Component / Module Diagram** — Subsystems and modules as nodes,
   dependencies as labeled edges. Use `flowchart` or `graph`.
2. **Entity-Relationship Diagram** — Entities, key attributes, and
   relationships. Use `erDiagram`.
3. **Dependency Graph** — Module-to-module dependencies with edge labels
   describing the nature of each dependency.

Optional diagrams when they add clarity:
- State machine diagrams for lifecycle flows.
- Sequence diagrams for multi-system interactions only.

Diagram guidelines:
- 5–12 nodes maximum per diagram.
- Label every edge.
- One concern per diagram — don't overload.
- Diagrams should be understandable without reading the surrounding prose.

## Dependency Analysis

Every architecture version must include an explicit dependency graph as a
Mermaid diagram. This is a directed graph where:

- **Nodes** are modules or subsystems (as defined in the module design).
- **Edges** are dependencies (A → B means A depends on B).
- **Edge labels** describe the nature of the dependency (calls, imports,
  reads data from, publishes events to).

### What to Check in a Dependency Graph

- **No cycles.** If the graph has cycles, the involved modules cannot
  be understood, tested, or deployed independently.
- **Reasonable fan-out.** No module should depend on more than 4–5 others
  without justification.
- **Stable core.** The most-depended-upon modules should be the most
  stable (least likely to change). If a frequently-changing module is
  depended on by many others, the architecture is fragile.
- **Clear layers.** Dependencies should generally flow in one direction. A
  lower layer depending on a higher layer is a red flag.

## Module Interfaces

Interfaces are described at the **contract level**, not the implementation
level:

- **What the module does** (its responsibility).
- **What it depends on** (other modules, external systems).
- **What it guarantees** (key invariants, error handling approach).
- **What it does NOT do** (explicit boundary).

Do not list function signatures, method inventories, or parameter types in
the architecture document. Those details change frequently and belong in
code documentation or the Sprint Changes section or ticket plans.

## Design Rationale

Architectural decisions should be documented with rationale. For each
significant decision, capture:

1. **Decision**: What was decided.
2. **Context**: What constraints, requirements, or trade-offs motivated it.
3. **Alternatives considered**: What other approaches were evaluated.
4. **Why this choice**: What makes this option better given the context.
5. **Consequences**: What trade-offs or limitations this decision introduces.

A "significant decision" is one where:

- A reasonable engineer might have chosen differently.
- The choice constrains future options.
- Reversing the decision later would be expensive.

Not every choice needs rationale. Choosing Python for a Python project does
not. Choosing a synchronous architecture over an event-driven one does.

Design rationale is cumulative across architecture versions. When a new
version changes a previous decision, the new rationale should reference the
old decision and explain what changed.

## Anti-Patterns to Flag

Both the architect and architecture-reviewer should watch for these:

- **God component**: One component that does most of the work or knows about
  most of the system.
- **Shotgun surgery**: A single logical change requires touching many
  components — usually a sign of misplaced responsibilities.
- **Feature envy**: A component that constantly reaches into another
  component's data — the behavior probably belongs in the other component.
- **Shared mutable state**: Multiple components reading and writing the same
  data without a clear owner.
- **Circular dependencies**: A → B → C → A. The components cannot be
  understood independently.
- **Leaky abstraction**: An interface that forces consumers to understand
  implementation details (e.g., exposing database IDs, raw SQL errors, or
  internal data structures).
- **Speculative generality**: Abstractions, configuration options, or
  extension points that exist for hypothetical future needs rather than
  current requirements.
