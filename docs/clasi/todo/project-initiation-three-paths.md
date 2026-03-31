---
status: pending
---

# Project Initiation: Three Paths and Document Hierarchy

## Problem

The current process produces an overview.md and jumps straight to
sprints. There's no formal specification document, no top-level
feature list, and no initial architecture before sprint planning
begins. When the stakeholder provides a detailed spec, it gets
read once and the detail is lost as context compresses.

## Three Entry Paths

### Path 1: Interview the stakeholder

The requirements-narrator interviews the stakeholder and produces
the project documents from the conversation.

### Path 2: Receive a spec

The stakeholder provides a written specification (like
guessing-game-spec.md). The requirements-narrator reads it and
extracts the project documents from it.

### Path 3: Existing project, new TODOs

The project already has a spec and architecture. The stakeholder
provides new TODOs to incorporate. Skip to roadmap planning.

## Document Hierarchy

By the time sprint planning begins, all of these should exist:

### 1. overview.md (small, ~1 page)

High-level summary of what the project is and why it exists.
Handed to agents that need context but not detail — sprint-planner,
sprint-executor, code-monkey. Think of it as the elevator pitch.

### 2. specification.md (medium, features without use cases)

The full feature specification. What the system does, how it
behaves, what the rules are. Detailed enough to implement from.
This is the stakeholder's intent preserved as a formal artifact.

The project-manager works from this document when planning the
roadmap. It contains everything needed to decide what goes in
which sprint.

If the stakeholder provided a spec file, specification.md may be
that file preserved verbatim, or it may be a cleaned-up extraction.

### 3. usecases.md (medium, numbered use cases)

Extracted from the specification. Numbered UC-NNN format with
actors, preconditions, flows, postconditions. These are the
testable scenarios that drive ticket acceptance criteria.

### 4. architecture.md (initial, from architect)

The architect reads the specification and use cases and produces
the first architecture document. This establishes the module
structure, data model, component relationships, and technology
stack before any sprint begins.

This is not a sprint architecture-update — it's the baseline
architecture for the project.

## Who Gets What

| Agent | Documents it reads |
|-------|--------------------|
| project-manager | specification.md, architecture.md, TODO assessments |
| sprint-planner | overview.md, sprint.md (roadmap), TODO files |
| sprint architect | architecture.md, sprint.md, usecases.md, codebase |
| technical-lead | architecture-update.md, sprint.md, usecases.md |
| code-monkey | ticket, architecture-update.md, coding standards |

The key insight: the project-manager needs the **full specification**
because it's deciding how to decompose work. The sprint-planner needs
the **overview** because it just needs project context, not the full
detail — its detail comes from the specific sprint goals and TODOs.

## Process Flow

### Paths 1 and 2 (new project):

```
stakeholder input (interview or spec)
    → requirements-narrator produces:
        - overview.md
        - specification.md
        - usecases.md
    → team-lead dispatches to architect:
        - architect produces initial architecture.md
    → team-lead dispatches to project-architect:
        - assess each TODO/feature from spec
    → team-lead dispatches to project-manager:
        - reads specification.md + architecture.md + assessments
        - produces roadmap sprint.md files
    → sprint-by-sprint execution begins
```

### Path 3 (existing project, new TODOs):

```
stakeholder provides TODOs
    → team-lead dispatches to project-architect:
        - assess each TODO against existing codebase
    → team-lead dispatches to project-manager:
        - reads specification.md + assessments + current architecture
        - produces roadmap sprint.md files
    → sprint-by-sprint execution begins
```

## Changes Required

1. **requirements-narrator** needs to produce `specification.md`
   in addition to `overview.md` and `usecases.md`. When receiving
   a full spec from the stakeholder, it should preserve the detail
   in specification.md (not just summarize it into an overview).

2. **Initial architecture step** needs to happen before roadmap
   planning, not during the first sprint. The team-lead dispatches
   to the architect after requirements are done but before the
   project-manager plans sprints.

3. **Contract updates** for agents that reference these documents —
   sprint-planner's contract should list overview.md as input,
   project-manager's contract should list specification.md.

4. **create_overview MCP tool** may need to be renamed or extended
   to handle the full document set (overview + specification +
   usecases).
