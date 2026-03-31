---
status: pending
---

# Roadmap Planning Process with TODO Assessment

## Problem

The team-lead currently decides how to break TODOs into sprints using
its own judgment, with no specialized agent or structured assessment.
For complex projects with many TODOs, this produces poor sprint
boundaries — related work gets split, dependencies get missed, and
difficulty isn't accounted for.

## Proposed Process

### Step 1: Team-lead receives work

The stakeholder provides a spec, a set of TODOs, or both. The
team-lead moves TODOs to in-progress and ensures the spec is saved
as a project artifact.

### Step 2: Project architect assesses each TODO

A new **project-architect** agent reads each TODO against the current
codebase and architecture. For each TODO it produces an assessment:

- What the feature requires (new modules, API changes, data changes)
- What existing code it touches (list of files/modules affected)
- Difficulty estimate (small / medium / large)
- Dependencies on other TODOs
- Type of changes (new code, refactor, config, documentation)

Output: an assessment document (one per TODO, or combined).

This is a **different agent** from the sprint-level architect. The
project-architect works at the TODO/feature level across the whole
project. The sprint architect works at the implementation level within
a single sprint. They share architectural quality instructions but
have different agent definitions and different scopes.

### Step 3: Project manager plans the roadmap

A new **project-manager** agent (or renamed from the current one)
reads all TODO assessments, the spec, and the current architecture.
It groups TODOs into sprints based on:

- Related functionality (TODOs that touch the same modules)
- Dependency ordering (TODO A must land before TODO B)
- Incremental value (each sprint delivers working functionality)
- Difficulty balancing (don't pack all hard items in one sprint)

Output: roadmap-level sprint.md files (lightweight — goals, TODO
refs, rationale for grouping). Multiple sprints planned in one pass.

### Step 4: Sprint planner fills in detail

The existing sprint-planner takes one roadmap sprint and produces:

- Detailed goals and scope
- Use cases for this sprint
- Dispatches to sprint architect for architecture-update.md
- Dispatches to technical-lead for tickets

The sprint planner has access to the codebase, the TODO assessments,
and the project-architect's analysis.

### Step 5: Sprint architect writes architecture update

The existing **architect** agent (now called **sprint architect** to
distinguish from project architect) writes the sprint's
architecture-update.md — the focused design for this sprint's changes.

### Step 6: Normal flow continues

Architecture reviewer, technical-lead (tickets), sprint-executor,
code-monkey.

## New Agents

### project-architect

- **Tier**: 1 (domain controller) or 2 (task worker)
- **Purpose**: Assess TODOs against the codebase. Feature-level
  analysis, not sprint-level design.
- **Inputs**: TODO files, current architecture, codebase access
- **Outputs**: Assessment document per TODO
- **Model**: opus (needs deep codebase understanding)
- **Shares with sprint architect**: architectural quality instructions,
  coding standards. But has its own agent.md with different scope
  and output format.

### project-manager

- **Tier**: 1 (domain controller)
- **Purpose**: Plan the roadmap — which TODOs go in which sprints.
- **Inputs**: TODO assessments, spec, current architecture
- **Outputs**: Roadmap sprint.md files (one per sprint, lightweight)
- **Model**: sonnet (organizational, not deeply technical)
- **Does NOT need**: codebase access. Works from assessments, not code.

## What Changes

- The team-lead's delegation map gains two new edges:
  dispatch_to_project_architect and dispatch_to_project_manager
- The current architect agent is renamed to sprint-architect
  (or just keeps the name "architect" since it's sprint-scoped)
- The project-architect is a new agent with its own agent.md and
  contract.yaml
- Shared architectural instructions (quality criteria, diagram
  standards, etc.) stay in `instructions/` and are referenced by
  both architect agents

## What Doesn't Change

- Sprint-planner, sprint-executor, code-monkey — unchanged
- The sprint-level architect role — same work, just clearer name
- Ticket structure, TODO lifecycle, close-sprint flow
