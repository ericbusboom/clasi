---
id: "019"
title: "TDD and Systematic Debugging"
status: planning
branch: sprint/019-tdd-and-systematic-debugging
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 019: TDD and Systematic Debugging

## Goals

Introduce TDD (test-driven development) as an available development
methodology and add a structured debugging protocol. These are the two
highest-impact standalone improvements identified from the Superpowers
plugin analysis. TDD is offered as an option that agents or stakeholders
can invoke, not a mandatory default.

## Problem

CLASI requires tests as a completion gate but allows implement-first,
test-after workflows. This means tests become retroactive verification
rather than design tools — interface problems are caught late. Additionally,
CLASI has no structured workflow for when things go wrong during
development. Agents make rapid speculative changes when tests fail,
often making things worse.

## Solution

Two new skills and updates to existing process docs:

1. **TDD cycle skill** (`skills/tdd-cycle.md`) — Defines the
   red-green-refactor workflow as an available option. Write failing
   test, confirm failure, write minimal code, confirm pass, refactor,
   commit at green. Can be invoked explicitly by the stakeholder or
   agent when appropriate.

2. **Systematic debugging skill** (`skills/systematic-debugging.md`) —
   Defines a four-phase protocol: evidence gathering, pattern analysis,
   hypothesis testing, root cause fix. Caps fix attempts at three before
   requiring escalation.

3. **Update execute-ticket** — Reference both skills: TDD as an
   available option for the implementation phase, debugging when tests
   fail or implementation hits problems.

4. **Update testing instruction** — Reference TDD as an available
   method, add guidance on when TDD is most useful vs when
   implement-then-test is fine.

Reference: Read `tdd.md` and `systematic-debugging.md` from
github.com/obra/superpowers for implementation details and edge cases.

## Success Criteria

- TDD cycle skill exists with complete red-green-refactor workflow
- Debugging skill exists with four-phase protocol and three-attempt cap
- execute-ticket references both skills at appropriate points
- Testing instruction updated to reference TDD as available option
- Guidance exists for when TDD is most useful vs implement-then-test

## Scope

### In Scope

- New skill: `tdd-cycle.md`
- New skill: `systematic-debugging.md`
- Modify skill: `execute-ticket.md` (reference TDD and debugging)
- Modify instruction: `testing.md` (TDD as available option)
- Modify instruction: `software-engineering.md` (debugging reference)

### Out of Scope

- Commit discipline changes (sprint 020)
- Subagent dispatch (sprint 022)
- Code changes to Python modules (these are all content files)

## Test Strategy

Content-only sprint — no Python code changes. Verification:
- `uv run pytest tests/unit/test_process_tools.py` (skill listing)
- Manual review of skill and instruction content

## Architecture Notes

These are bundled content changes only (skills/ and instructions/
directories). No changes to Python modules, MCP tools, templates, or
the state database.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001 — Create tdd-cycle skill definition** [SUC-001]
   Create `skills/tdd-cycle.md` defining red-green-refactor as optional
   workflow. Includes when-to-use guidance and unexpected-pass handling.

2. **002 — Create systematic-debugging skill definition** [SUC-002]
   Create `skills/systematic-debugging.md` with four-phase debugging
   protocol, three-attempt cap, escalation procedure, and audit trail.

3. **003 — Update execute-ticket, testing, and SE instructions** [SUC-003]
   (depends on 001, 002) Update `execute-ticket.md` to reference
   tdd-cycle as option and debugging skill. Update `testing.md` to
   reference TDD as available method. Update `software-engineering.md`
   to reference debugging protocol and list new skills.
