---
id: "017"
title: "Process Compliance Reinforcement"
status: planning
branch: sprint/017-process-compliance-reinforcement
use-cases:
  - SUC-017-001
  - SUC-017-002
---

# Sprint 017: Process Compliance Reinforcement

## Goals

Reduce agent process violations by eliminating the indirection between
CLAUDE.md and AGENTS.md, and by embedding a process reminder in every
planning document template that agents read during sprint work.

## Problem

Agents repeatedly ignore SE process instructions (answering from memory
instead of consulting documented procedures). Two reflections document
the same root cause: "ignored instruction." The CLASI block lives in
AGENTS.md, referenced via `@AGENTS.md` from CLAUDE.md. Agents may
deprioritize this secondary file. Additionally, when agents read sprint
docs, tickets, or architecture documents during execution, there is no
reminder to consult the process — the only reminders are in CLAUDE.md
and AGENTS.md, which may have faded from active context.

## Solution

1. **Inline the CLASI block into CLAUDE.md** — The `clasi init` command
   will write the CLASI section directly into CLAUDE.md (using the
   existing `<!-- CLASI:START/END -->` markers for updates). Remove the
   AGENTS.md creation step.

2. **Add a process reminder to document templates** — Add a single-line
   HTML comment to every template (sprint, architecture, ticket, use
   cases) reminding agents to consult the SE process before making
   changes. This provides redundant reinforcement at the point where
   agents are actively reading planning artifacts.

## Success Criteria

- `clasi init` writes the CLASI block into CLAUDE.md, not AGENTS.md
- `clasi init` no longer creates or updates AGENTS.md
- All four document templates contain the process reminder line
- All existing tests pass; new tests cover the changed init behavior

## Scope

### In Scope

- `init_command.py` — rewrite to target CLAUDE.md instead of AGENTS.md
- `claude_agent_skills/init/claude-md.md` — replace with full CLASI block
- `claude_agent_skills/init/agents-section.md` — remove or repurpose
- Four templates: `sprint.md`, `sprint-architecture.md`, `ticket.md`,
  `sprint-usecases.md` — add reminder line
- Tests for init command behavior
- Update `agents-section.md` (the init template) to reflect new target

### Out of Scope

- Changing the AGENTS.md in this repository (it stays for now)
- Hooks or enforcement mechanisms beyond instructions
- Changes to the MCP server or artifact tools

## Test Strategy

Unit tests for `init_command.py` covering:
- Fresh init writes CLASI block into CLAUDE.md
- Re-init updates existing CLASI section in CLAUDE.md
- No AGENTS.md is created or modified
- Template content includes the reminder line

## Architecture Notes

The init command's file ownership changes from AGENTS.md to CLAUDE.md.
The `<!-- CLASI:START/END -->` markers are reused for section replacement.
Templates gain a single HTML comment line — no structural changes.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

(To be created after sprint approval.)
