---
id: '003'
title: SE Process Tooling Improvements
status: done
branch: sprint/003-se-process-tooling-improvements
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
todos:
- consolidate-agent-definitions-and-skills.md
- project-init-docs-in-design-dir.md
- project-initiation-dispatch-to-subagent.md
- sprint-planner-backfill-tickets-in-sprint-md.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 003: SE Process Tooling Improvements

## Goals

Improve the CLASI SE process tooling across four related areas:

1. **Consolidate agent definitions** — Move `plugin/` into the `clasi` Python package as
   `clasi/plugin/`, eliminating the dual-source problem between `plugin/agents/` and
   `clasi/agents/`. Remove `plugin/` from the repo root after migration.

2. **Fix project initiation output directory** — Verify that the `project-initiation`
   skill and `.claude/skills/project-initiation/SKILL.md` direct output to
   `docs/clasi/design/` and fix any deviations.

3. **Dispatch project initiation to a subagent** — Refactor the `project-initiation`
   skill so the team-lead dispatches to a subagent (sprint-planner or a dedicated
   initiation agent) rather than writing documents directly, preserving the
   team-lead's "never write content" rule.

4. **Backfill ticket summary into sprint.md** — After the sprint-planner creates
   tickets, it should update the `## Tickets` section of `sprint.md` with a summary
   table (ticket number, title, dependencies, parallel execution group).

## Problem

The CLASI tooling has accumulated several structural inconsistencies:

- Two separate agent definition trees (`plugin/agents/` and `clasi/agents/`) define
  overlapping agents (e.g., sprint-planner appears in both), guaranteeing drift.
  `plugin/` at the repo root is not proper Python package structure.

- The `project-initiation` skill has historically written documents to inconsistent
  locations. The team-lead invoking the skill also violates its own "never write
  content directly" rule.

- After sprint planning, `sprint.md` has an empty `## Tickets` placeholder, requiring
  a separate lookup to understand what tickets exist and how they relate.

## Solution

- Move `plugin/` to `clasi/plugin/` (package data). Update `_PLUGIN_DIR` in
  `init_command.py` to point to the new location. Audit the 10 extra agents in
  `clasi/agents/` to determine which are used by contracts; migrate the useful ones
  and remove the rest. Remove the old `plugin/` directory.

- Verify the installed `project-initiation` skill (`plugin/skills/project-initiation/
  SKILL.md`) already specifies `docs/clasi/design/` as the output directory. If the
  `.claude/skills/` version diverges, regenerate it via `clasi init`.

- Update `project-initiation` SKILL.md to instruct the team-lead to dispatch to the
  sprint-planner (or a new project-initiation agent) rather than writing the three
  documents itself.

- Update `clasi/templates/sprint.md` to include an empty ticket summary table in
  `## Tickets`. Update the sprint-planner agent definition (`plugin/agents/sprint-planner/
  agent.md`) to add a step after ticket creation that populates the table. Also update
  `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` accordingly.

## Success Criteria

- `clasi/plugin/` exists and contains all content previously in `plugin/`. The old
  `plugin/` directory is removed. `clasi init` still works correctly.
- `contracts.py` (or equivalent) references `clasi/plugin/` not `clasi/agents/`.
- The installed `project-initiation` skill dispatches to a subagent; the team-lead
  does not write documents directly when invoking it.
- All project initiation output goes to `docs/clasi/design/`.
- After `create_tickets` step, the `## Tickets` section in `sprint.md` contains a
  populated summary table.
- All existing tests pass.

## Scope

### In Scope

- Moving `plugin/` to `clasi/plugin/` and updating all references
- Auditing `clasi/agents/` (13 agents) — keeping used ones, removing vestigial ones
- Deduplicating sprint-planner process descriptions (one source of truth per agent)
- Updating `project-initiation` SKILL.md to dispatch to a subagent
- Confirming `docs/clasi/design/` is the output directory in the skill
- Adding ticket summary table template to `clasi/templates/sprint.md`
- Adding ticket table backfill step to sprint-planner agent definition
- Adding ticket table backfill step to `plan-sprint.md` internal skill

### Out of Scope

- Wiring up the 10 extra `clasi/agents/` agents into the live Claude Code process
- Rewriting the contracts system
- Changes to MCP server logic
- Creating a new dedicated project-initiation agent (the sprint-planner can cover it)

## Test Strategy

- Run `uv run pytest` to confirm existing tests pass after file moves.
- Manually verify `clasi init` writes correctly from the new `clasi/plugin/` path.
- Review the installed `project-initiation` skill to confirm subagent dispatch wording.
- Review sprint-planner agent.md and sprint.md template for ticket table presence.

## Architecture Notes

- `_PLUGIN_DIR` in `init_command.py` already has a fallback: it first checks
  `Path(__file__).parent.parent / "plugin"` (dev layout), then
  `Path(__file__).parent / "plugin"` (installed package layout). After the move,
  the installed layout path becomes the primary and the dev fallback is removed.
- The `clasi/agents/` hierarchy is used by `contracts.py` for contract validation.
  Any agents eliminated must also be removed from contract configuration.
- Process descriptions (5-phase workflow) should live in the agent's `agent.md` only;
  skill SKILL.md files should reference the agent, not repeat the workflow.

## GitHub Issues

(None linked yet.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Move plugin/ into clasi/plugin/ package data | — | 1 |
| 002 | Fix project-initiation output directory to docs/clasi/design/ | — | 1 |
| 003 | Update project-initiation skill to dispatch to subagent | 002 | 2 |
| 004 | Add ticket summary table backfill to sprint-planner and sprint template | — | 1 |

Tickets in the same Group can execute in parallel.
