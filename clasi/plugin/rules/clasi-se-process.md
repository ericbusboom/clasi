# CLASI SE Process

This project uses the CLASI software engineering process, served via MCP
tools.

## Process Overview

The SE process has four stages:

1. **Stage 1a — Requirements**: Elicit requirements, produce brief and use cases
2. **Stage 1b — Architecture**: Produce architecture document from brief and use cases
3. **Stage 2 — Ticketing**: Break architecture into actionable tickets
4. **Stage 3 — Implementation**: Execute tickets in sprints

Work is organized into **sprints** — each sprint is a directory containing
planning documents and tickets.

## MCP Tools Reference

Use these MCP tools (provided by the `clasi` server) to interact with the
SE process:

### SE Process Access

| Tool | Description |
|------|-------------|
| `get_activity_guide(activity)` | Tailored guidance for an activity |
| `list_agents` | List available agent definitions |
| `list_skills` | List available skill definitions |
| `list_instructions` | List available instruction files |
| `get_agent_definition(name)` | Full agent definition |
| `get_skill_definition(name)` | Full skill definition |
| `get_instruction(name)` | Full instruction content |

### Artifact Management

| Tool | Description |
|------|-------------|
| `create_sprint(title)` | Create a new sprint directory |
| `create_ticket(sprint_id, title)` | Create a ticket in a sprint |
| `list_sprints(status?)` | List sprints |
| `list_tickets(sprint_id?, status?)` | List tickets |
| `get_sprint_status(sprint_id)` | Sprint summary with ticket counts |
| `update_ticket_status(path, status)` | Update ticket status |
| `move_ticket_to_done(path)` | Move completed ticket to done/ |
| `close_sprint(sprint_id)` | Close and archive a sprint |

## Getting Started

1. Use `get_activity_guide("requirements")` when starting a new project
3. Use `create_sprint(title)` to begin a new sprint
