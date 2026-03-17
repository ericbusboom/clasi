---
id: "022"
title: "Subagent Dispatch and Two-Stage Review"
status: active
branch: sprint/022-subagent-dispatch-and-two-stage-review
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 022: Subagent Dispatch and Two-Stage Review

## Goals

Introduce a real subagent dispatch protocol that spawns fresh Claude Code
subagents via the Agent tool with curated context, and restructure code
review into two explicit phases (correctness then quality). This is the
single largest architectural change to the CLASI agent model.

## Problem

CLASI defines agent roles as personas the same Claude instance adopts.
Context bleeds between roles, there is no true isolation, and no
parallelism. Code review is a single undifferentiated pass where
correctness and quality issues are mixed, and correctness checks can be
skipped when context is long.

## Solution

1. **Dispatch-subagent skill** — Defines a controller/worker pattern.
   The controller curates context (only relevant files, specs,
   constraints), dispatches a fresh subagent via the Agent tool,
   and reviews results.

2. **Subagent-protocol instruction** — Rules for context curation:
   what to include (relevant source, ticket, acceptance criteria,
   architecture decisions, coding standards) and what to exclude
   (conversation history, other tickets, debugging logs).

3. **Two-stage code review** — Restructure code-reviewer agent into
   Phase 1 (correctness vs acceptance criteria, binary pass/fail) and
   Phase 2 (quality vs coding standards, severity-ranked issues).
   Phase 1 failure short-circuits.

4. **Review checklist template** — Structured output for code reviews,
   stored alongside tickets for auditability.

Reference: Read Superpowers `subagent-driven-development.md`,
`receiving-code-review.md`, and `dispatching-parallel-agents.md`.

## Success Criteria

- Dispatch-subagent skill defines controller/worker with context curation
- Subagent-protocol instruction defines include/exclude rules
- Code-reviewer agent restructured into two phases
- Review checklist template exists
- execute-ticket updated to use dispatch for implementation
- project-manager updated to use dispatch as primary method

## Scope

### In Scope

- New skill: `dispatch-subagent.md`
- New instruction: `subagent-protocol.md`
- New template: `review-checklist.md`
- Modify agent: `code-reviewer.md` (two-phase review)
- Modify agent: `project-manager.md` (dispatch-based execution)
- Modify skill: `execute-ticket.md` (dispatch instead of persona switch)

### Out of Scope

- Parallel execution (sprint 023)
- Changes to Python code or MCP tools
- Worktree management

## Test Strategy

Mostly content changes. The review-checklist template addition touches
`templates.py`. Verification:
- `uv run pytest` (skill/agent listing tests, template tests)
- Manual review of skill, instruction, agent, and template content

## Architecture Notes

This sprint changes the fundamental execution model from persona-switching
to true subagent dispatch. The Agent tool (built into Claude Code) is the
dispatch mechanism — no custom Python code needed for dispatch itself.

The review checklist template will be added to `templates/` directory
and loaded by the templates module. This is the only Python code change
(adding a template constant to `templates.py`).

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001** — Create dispatch-subagent skill and subagent-protocol instruction
   - use-cases: SUC-001, SUC-003 | depends-on: none
2. **002** — Restructure code-reviewer agent for two-stage review
   - use-cases: SUC-002 | depends-on: 001
3. **003** — Create review-checklist template
   - use-cases: SUC-002 | depends-on: 002
4. **004** — Update project-manager and execute-ticket for dispatch model
   - use-cases: SUC-001 | depends-on: 001, 002
