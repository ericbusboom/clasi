# CLASI SE Process Overview

## Issues vs Tickets

Two distinct concepts govern how work is tracked:

- An **issue** is a proposed change to the system — an idea, bug report,
  enhancement request, or task captured before sprint planning. Issues live
  in `.clasi/issues/`. They are the raw material that sprint planning draws
  from. A single issue may spawn one or more tickets, or be deferred
  indefinitely.

- A **ticket** is a concrete implementation step within a sprint. Tickets
  live in `.clasi/sprints/<sprint-id>/tickets/`. A ticket is derived from
  (and often closes) an issue, but it is scoped to what can be done in a
  single sprint and carries acceptance criteria, a plan, and a status that
  the SE process enforces.

In short: issues propose; tickets implement.

## Process Stages

1. **Project Initiation**: Process written spec into project documents
   - Agent: `project-manager` (initiation mode) → overview.md, specification.md, usecases.md
2. **Issue Assessment**: Assess issues against codebase for impact analysis
   - Agent: `project-architect` → difficulty estimates, dependencies
3. **Roadmap Planning**: Group assessed issues into sprint roadmap
   - Agent: `project-manager` (roadmap mode) → lightweight sprint.md files
4. **Sprint Detail Planning**: Full planning for the next sprint to execute
   - Skill: `plan-sprint` | Agent: `sprint-planner` → usecases, architecture, tickets
5. **Sprint Execution**: Execute tickets in a planned sprint
   - Skill: `execute-ticket` | Agents: `sprint-executor`, `code-monkey`, `code-reviewer`

## Available Agents

{agent_lines}

## Available Skills

{skill_lines}

## Available Instructions

{instruction_lines}

## MCP Tools Quick Reference

### SE Process Access (this tool group)
- `get_se_overview()` — This overview
- `get_activity_guide(activity)` — Tailored guidance for a specific activity
- `list_agents()` / `get_agent_definition(name)` — Agent definitions
- `list_skills()` / `get_skill_definition(name)` — Skill definitions
- `list_instructions()` / `get_instruction(name)` — Instruction files

### Artifact Management
- `create_sprint(title)` / `list_sprints()` / `get_sprint_status(sprint_id)` — Sprint management
- `create_ticket(sprint_id, title)` / `list_tickets()` — Ticket management
- `update_ticket_status(path, status)` / `move_ticket_to_done(path)` — Ticket lifecycle
- `close_sprint(sprint_id)` — Sprint closure
- `create_brief()` / `create_use_cases()` — Top-level artifacts
