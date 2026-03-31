# CLASI SE Process Overview

## Process Stages

1. **Stage 1a — Requirements**: Process specification, produce project documents
   - Agent: `project-manager` (initiation mode)
2. **Stage 1b — Architecture**: Design architecture per sprint
   - Skill: `plan-sprint` (architecture step) | Agent: `architect`
3. **Sprints**: Plan and execute sprints
   - Skills: `plan-sprint`, `close-sprint` | Agents: `sprint-planner`, `sprint-executor`
4. **Stage 2 — Ticketing**: Break plan into numbered tickets
   - Skill: `create-tickets` | Agent: `technical-lead`
5. **Stage 3 — Implementation**: Execute tickets (plan → implement → test → review → done)
   - Skill: `execute-ticket` | Agents: `code-monkey`, `code-reviewer`

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
