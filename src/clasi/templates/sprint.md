---
id: "{id}"
title: "{title}"
status: roadmap
branch: sprint/{id}-{slug}
worktree: false
use-cases: []
issues: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint {id}: {title}

## Goals

(Describe what this sprint aims to accomplish.)

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

(List what is included in this sprint.)

### Out of Scope

(List what is explicitly excluded.)

## Test Strategy

(Describe the overall testing approach for this sprint: what types of tests,
what areas need coverage, any integration or system-level testing needed.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
