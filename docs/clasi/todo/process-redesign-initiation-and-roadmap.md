---
status: pending
---

# Redesign Project Initiation and Roadmap Planning

Consolidates three related TODOs:
- project-initiation-three-paths.md
- roadmap-planning-process.md
- stakeholder-plan-passthrough.md

## Problem

The current process has gaps between receiving work and starting
sprints:

1. **No specification preservation.** When the stakeholder provides a
   detailed spec, it gets read once and summarized into an overview.
   The detail is lost as context compresses. The spec should be
   preserved as `specification.md`.

2. **No structured roadmap planning.** The team-lead decides how to
   break TODOs into sprints using its own judgment. There's no agent
   that assesses TODO difficulty/scope or plans sprint boundaries.

3. **No initial architecture.** Architecture happens per-sprint, but
   there's no baseline architecture before the first sprint. The
   project-manager needs an architecture to plan the roadmap.

## Two Entry Paths

### Path 1: Receive a written spec
Requirements-narrator reads the spec, extracts project documents,
preserves the full spec as specification.md. No stakeholder interview
— the spec is the input. (Stakeholder interviews happen outside CLASI,
in the Claude project or conversation that produces the spec.)

### Path 2: Existing project, new TODOs
Spec and architecture already exist. Skip to roadmap planning.

## Document Hierarchy

Before sprint planning begins, these documents should exist:

| Document | Size | Purpose | Who reads it |
|----------|------|---------|-------------|
| overview.md | ~1 page | Elevator pitch | sprint-planner, code-monkey |
| specification.md | full | Complete feature spec | project-manager |
| usecases.md | medium | Numbered UC-NNN scenarios | sprint-planner, technical-lead |
| architecture.md | medium | Baseline architecture | project-architect, sprint architect |

## Process Flow (Path 1 — new project with spec)

```
1. Stakeholder provides a written specification
       │
2. project-manager produces:
       ├── overview.md (summary)
       ├── specification.md (full detail, preserved)
       └── usecases.md (extracted use cases)
       │
3. architect produces:
       └── architecture.md (initial baseline)
       │
4. project-architect assesses each TODO/feature:
       └── assessment per TODO (difficulty, scope, dependencies)
       │
5. project-manager plans roadmap:
       ├── reads specification.md + architecture.md + assessments
       └── produces roadmap sprint.md files (one per sprint)
       │
6. Sprint-by-sprint execution:
       └── sprint-planner → architect → reviewer → technical-lead
           → sprint-executor → code-monkey
```

## Process Flow (Path 3 — new TODOs on existing project)

```
1. Stakeholder provides TODOs
       │
2. project-architect assesses each TODO
       │
3. project-manager plans roadmap from assessments
       │
4. Sprint-by-sprint execution
```

## New Agents

### project-architect (tier 2, model: opus)

Assesses TODOs against the codebase. Per-TODO analysis:
- What the feature requires (new modules, API changes)
- What existing code it touches
- Difficulty estimate (small / medium / large)
- Dependencies on other TODOs
- Type of changes (new code, refactor, config, docs)

Different from the sprint architect — works at the feature level
across the whole project, not at the implementation level within
a sprint. Shares architectural quality instructions with sprint
architect but has its own agent.md.

### project-manager (tier 1, model: sonnet)

Owns all pre-sprint project-level work. Two modes:

**Mode 1: Project initiation.** Receives a written spec from the
stakeholder. Produces:
- overview.md (summary for context)
- specification.md (full detail, preserved)
- usecases.md (extracted use cases)

This absorbs the requirements-narrator role. The requirements-narrator
agent is removed.

**Mode 2: Roadmap planning.** Reads:
- specification.md (full detail)
- architecture.md (baseline)
- TODO assessments (from project-architect)

Groups TODOs into sprints based on:
- Related functionality (same modules)
- Dependency ordering
- Incremental value delivery
- Difficulty balancing

Does NOT need codebase access — works from assessments and specs.
Output: roadmap sprint.md files (lightweight — goals, TODO refs).

## Changes Required

1. **Remove requirements-narrator.** Its role (extracting overview,
   spec, and use cases) is absorbed by the project-manager. Delete
   the agent directory, contract, dispatch template, and dispatch tool.
   Remove from team-lead delegation map.

2. **Create project-manager agent** with two modes: initiation
   (extract documents from spec) and roadmap (plan sprints from
   assessments). Agent.md, contract.yaml, dispatch template.

3. **Create project-architect agent** for TODO assessment. Agent.md,
   contract.yaml, dispatch template.

4. **Initial architecture**: Team-lead dispatches to architect after
   project-manager produces documents but before roadmap planning.

5. **Team-lead delegation map**: Remove dispatch_to_requirements_narrator.
   Add dispatch_to_project_architect and dispatch_to_project_manager.

6. **Sprint-planner contract**: Input is overview.md (not the full
   spec). Gets project context, not implementation detail.

7. **Dispatch templates and contracts**: For project-manager and
   project-architect.

## What Doesn't Change

- Sprint-planner, sprint-executor, code-monkey — unchanged
- The sprint-level architect — same work, same name
- Ticket structure, TODO lifecycle, close-sprint flow
