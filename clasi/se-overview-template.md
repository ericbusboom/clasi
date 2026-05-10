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
   - The `architecture-update.md` is authored before tickets are created; per-sprint files accumulate as a chronological historical record.
5. **Sprint Execution**: Execute tickets in a planned sprint
   - Skill: `execute-ticket` | Agents: `sprint-executor`, `code-monkey`, `code-reviewer`

## Available Agents

{agent_lines}

## Available Skills

{skill_lines}

## Available Instructions

{instruction_lines}

## Exception protocol

When a lower agent (programmer or sprint-planner) cannot make progress after
three failed fix attempts, it must **throw a ticket exception** rather than
continuing to guess.

### Threshold

After three failed fix attempts on the same problem, STOP. Do not make a
fourth attempt. Use the `throw_ticket_exception` MCP tool to record the
block and escalate.

### Payload schema

`throw_ticket_exception` writes an `exception:` block to the ticket
frontmatter and sets `status: exception`:

```yaml
exception:
  thrown_by: programmer        # "programmer" or "sprint-planner"
  thrown_at: 2026-05-07T14:23:00Z
  attempted: |
    Summary of what was tried across three attempts.
  conflict: |
    Exact description of what blocked progress — architecture decision,
    missing dependency, contradictory requirements, etc.
  surface: internal            # "internal" or "user-visible"
```

### Ticket as carrier

The ticket file itself is the exception carrier. Its `status` is set to
`exception`; the `exception:` block records the full context. The ticket is
**not** moved to `done/` — it stays in `tickets/` so the team-lead can
inspect and route it.

### Team-lead routing branches

When the team-lead sees a ticket with `status: exception`, it must choose one
of the following routing branches before resuming execution:

| `surface` value | Routing |
|-----------------|---------|
| `internal`      | Team-lead resolves autonomously: update architecture, revise ticket, reopen it with `reopen_ticket`, then continue. |
| `user-visible`  | Team-lead escalates to the stakeholder: present the conflict and wait for a decision before taking any further action. |

### Revision naming convention

When reopening an exception ticket after resolution, update the ticket title
or add a `## Revision` section describing what changed. Do not silently
re-execute the same plan that failed.

### Calibration signal

A sprint with more than one or two exception tickets signals a planning
problem. Escalate to the stakeholder for scope review rather than resolving
each exception in isolation.

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
