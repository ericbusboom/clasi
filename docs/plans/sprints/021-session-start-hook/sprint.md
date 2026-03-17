---
id: "021"
title: "Session-Start Hook"
status: planning
branch: sprint/021-session-start-hook
use-cases:
  - SUC-001
  - SUC-002
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 021: Session-Start Hook

## Goals

Replace the prose directive in CLAUDE.md ("you MUST call
`get_se_overview()`") with a mechanical enforcement mechanism: a
session-start hook that automatically triggers SE process loading before
the agent sees any user input.

## Problem

CLASI relies on a prose directive in CLAUDE.md/AGENTS.md that the agent
must call `get_se_overview()` before doing any work. This is a request,
not enforcement. Agents can forget, skip it, or get distracted by the
user's prompt. Multiple reflections have documented process-loading
failures caused by this gap.

## Solution

Create a Claude Code hooks configuration that runs at session start.
The hook outputs a message that triggers the agent to load the SE
process. Install this hook during `clasi init`.

The CLAUDE.md directive remains as belt-and-suspenders backup.

Reference: Read Superpowers `session-start.sh` hook implementation.

## Success Criteria

- Hook configuration is created during `clasi init`
- Hook triggers SE process loading at session start
- Existing CLAUDE.md directive remains as backup
- Init is idempotent (re-running doesn't duplicate hooks)

## Scope

### In Scope

- Claude Code hooks configuration (`.claude/hooks/` or hooks in settings)
- Modify `init_command.py` to install hook during init
- Unit tests for hook installation

### Out of Scope

- Removing the CLAUDE.md directive (kept as backup)
- Hook mechanisms for non-Claude-Code environments

## Test Strategy

- Unit tests for init_command.py hook installation logic
- Verify idempotency (run init twice, check no duplication)
- `uv run pytest`

## Architecture Notes

This sprint modifies `init_command.py` (Python code change) to create
a hooks configuration file. Need to verify the exact hook mechanism
available in current Claude Code versions — hooks may use
`.claude/settings.local.json` or a dedicated hooks directory.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001** — Research Claude Code hooks mechanism
   - use-cases: [SUC-001], depends-on: []
   - Research hook format, review Superpowers session-start.sh, document findings for ticket 002
2. **002** — Create session-start hook template and install in init
   - use-cases: [SUC-001, SUC-002], depends-on: [001]
   - Create hook content, modify init_command.py to install it, ensure idempotency
3. **003** — Unit tests for hook installation
   - use-cases: [SUC-002], depends-on: [002]
   - Unit tests for init_command.py: hook creation, idempotency (run twice = same result), correct format
