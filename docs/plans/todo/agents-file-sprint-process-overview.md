---
status: pending
---

# Add Sprint Process Overview to AGENTS.md

The CLASI block injected into the project's `AGENTS.md` file by `init_command.py` should include a high-level overview of the sprint process steps. Currently the AGENTS.md block is minimal — it tells the agent that CLASI exists and points it at the `/se` skill, but doesn't lay out the actual workflow.

## Problem

Every time an agent reads `AGENTS.md`, it should immediately understand the full sprint lifecycle — what steps to follow, in what order, and which MCP tools to use at each step. Without this, the agent has to discover the process incrementally through tool calls, which leads to missed steps (e.g., skipping review tools, leaving files in draft status).

## What to Add

A numbered, high-level sprint process overview in the CLASI section of `AGENTS.md`. Something like:

1. **Create a sprint** — Use `create_sprint` to set up the sprint directory
2. **Gather requirements** — Incorporate pending TODOs (`list_todos`) and/or ask the user what the sprint should accomplish
3. **Write planning documents** — Fill in the three sprint documents:
   - `sprint.md` — Goals, scope, acceptance criteria
   - `usecases.md` — Use cases for this sprint
   - `technical-plan.md` — Architecture changes, component design
4. **Review gates** — Advance through architecture review and stakeholder review phases
5. **Run pre-execution review** — Use the sprint review tool to validate all planning artifacts are complete and correctly statused before proceeding
6. **Create tickets** — Use `create_ticket` to break the sprint into implementable tickets
7. **Implement tickets** — Execute each ticket, marking them done and moving to `tickets/done/`
8. **Run pre-close review** — Use the sprint review tool to validate all tickets are done, all files have real content (not template defaults), and all frontmatter statuses are correct
9. **Close the sprint** — Use `close_sprint` to finalize

## Key Requirements

- The process steps should reference the specific MCP tools to use
- Must explicitly mention the pre-execution and pre-close review tools (see TODO: `sprint-review-mcp-tools.md`)
- Should be concise enough to fit in `AGENTS.md` without overwhelming — this is a quick-reference checklist, not full documentation
- The agent should understand that skipping review steps is not acceptable
- Update `init_command.py` to include this content in the CLASI block it writes to `AGENTS.md`
