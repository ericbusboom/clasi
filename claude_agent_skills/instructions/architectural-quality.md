---
name: architectural-quality
description: Principles and criteria for evaluating architectural quality — referenced by the architect and architecture-reviewer agents
---

# Architectural Quality Guide

This guide defines the principles and criteria for evaluating architectural
quality. It is referenced by the **architect** (when designing and updating
the architecture) and the **architecture-reviewer** (when reviewing).

## Architecture as a Living Document

The system architecture is maintained as a versioned document in
`docs/plans/architecture/`. Each version represents the target state of the
system after a given sprint completes:

```
docs/plans/architecture/
  architecture-014.md   # Architecture at the end of sprint 014
  architecture-015.md   # Architecture at the end of sprint 015
  architecture-016.md   # Architecture at the end of sprint 016
  ...
```

The architecture version number **is** the sprint number. Each document
describes the architecture as it exists at the end of that sprint.

The architecture document describes **what the system is** — its components,
boundaries, interfaces, dependencies, data model, and design rationale. It
is not a plan of work; it is a specification of the system's structure.

The sprint's technical plan (`docs/plans/sprints/<sprint>/technical-plan.md`)
describes **what changes are being made** to move from the current
architecture version to the next one. Tickets are derived from the sprint
technical plan, not from the architecture document directly.

### Versioning Rules

- The initial architecture (produced during Stage 1b) is numbered `001`.
- Each sprint that changes the architecture produces a new version,
  numbered sequentially.
- Sprints that do not change the architecture (pure bug fixes, refactors
  within existing boundaries) do not produce a new version.
- The latest version is always the current target. Previous versions are
  retained as history.
- The architecture version number is independent of the sprint number.
  A sprint's technical plan references which architecture version it
  targets (e.g., "This sprint moves the system from architecture-002 to
  architecture-003").

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

1. **Architecture Overview** — High-level structure, component relationships,
   and the dependency map.
2. **Technology Stack** — Languages, frameworks, databases, infrastructure,
   with justifications against the brief's constraints.
3. **Component Design** — Each component with:
   - Purpose (one sentence, no "and")
   - Boundary (what is inside, what is outside)
   - Interface specification (operations, data shapes, error cases, invariants)
   - Use cases served
4. **Dependency Map** — Directed graph of component dependencies (see below).
5. **Data Model** — Key entities, relationships, storage approach, entity
   ownership by component.
6. **API Design** — Endpoints, request/response formats, authentication.
7. **Security Considerations** — Authentication, authorization, data
   protection.
8. **Design Rationale** — Significant decisions with alternatives and
   reasoning (see below).
9. **Open Questions** — Anything ambiguous, assumed, or requiring
   stakeholder input.

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
code documentation or sprint-level technical plans.

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
