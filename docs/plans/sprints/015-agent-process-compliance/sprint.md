---
id: "015"
title: "Agent Process Compliance"
status: planning
branch: sprint/015-agent-process-compliance
use-cases: [UC-007, UC-009, UC-010, UC-013]
---

# Sprint 015: Agent Process Compliance

## Goals

Harden the CLASI SE process so that agents reliably follow it without
stakeholder intervention. Address the systemic failures identified in 8
reflection documents (2026-02-11 through 2026-03-08).

## Problem

Analysis of all reflection documents shows every failure is category
`ignored-instruction`. Agents bypass the process, use wrong tools, skip
approval gates, and improvise workarounds when blocked. The process itself
is sound — agents just don't consult it at decision points.

Three failure modes:

1. **Process bypass** — agents start coding without checking for an active
   sprint/ticket (4 of 8 reflections)
2. **Wrong tool selection** — agents use generic tools instead of CLASI
   skills (2 of 8)
3. **Completion bias** — agents improvise workarounds instead of reporting
   blockers (2 of 8)

## Solution

1. Strengthen the `agents-section.md` template with mandatory gates and
   behavioral rules that interrupt the agent's flow at decision points.
2. Add automated sprint validation MCP tools that catch incomplete state.
3. Add an `/oop` skill for legitimate out-of-process quick fixes.
4. Improve quality-of-life in skills (narrative mode, Mermaid preference).

## Success Criteria

- `agents-section.md` contains mandatory `get_se_overview()` gate, pre-flight
  check, CLASI-first routing rule, stop-and-report rule, and sprint overview
- Sprint review MCP tools validate state at pre-execution, pre-close, and
  post-close checkpoints with actionable fix instructions
- `/oop` skill exists for out-of-process quick fixes
- Project initiation interview offers narrative mode
- Instructions reference Mermaid over ASCII for diagrams

## Scope

### In Scope

- `agents-section.md` template rewrites (process engagement rules, sprint
  overview, CLAUDE.md linkage improvements)
- Three sprint review MCP tools with structured error reporting
- `/oop` skill definition
- Narrative mode in `project-initiation` skill
- Mermaid preference in instruction/skill guidance
- Tests for sprint review tools

### Out of Scope

- Runtime enforcement (hooks, CI checks)
- Changes to the MCP server's phase state machine
- New agent definitions

## Test Strategy

Sprint review MCP tools require comprehensive unit tests:
- Happy path (correct sprint passes)
- Missing files, wrong frontmatter, template placeholders
- Ticket state issues (not done, not in done/ directory)
- Branch/checkout issues
- Regression tests against historical sprints in `sprints/done/`

Skill/instruction changes are documentation — verified by reading.

## Architecture Notes

- Sprint review tools are new MCP tool functions in the artifact_tools
  module, following the existing pattern of `close_sprint`, `get_sprint_status`
- They return structured JSON with `passed`, `issues[]` containing
  `severity`, `check`, `message`, `fix`, `path`
- `agents-section.md` changes propagate to new projects via `clasi init`;
  this project's AGENTS.md needs manual sync

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, technical plan)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **#001** — Rewrite agents-section.md with behavioral rules and sprint overview
2. **#002** — Add sprint review MCP tools with tests
3. **#003** — Create /oop out-of-process skill
4. **#004** — Add narrative mode to project-initiation skill
5. **#005** — Add Mermaid diagram preference to instructions and skills
6. **#006** — Sync project AGENTS.md with updated agents-section.md (depends: #001)
