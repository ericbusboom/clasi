---
id: "004"
title: "Team-lead identity binding"
status: todo
use-cases: []
depends-on: []
todo: "team-lead-identity-binding.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Team-lead identity binding

## Description

Update CLAUDE.md and AGENTS.md so the top-level Claude session knows it
IS the team-lead. Currently the process docs describe the roles but never
explicitly state "you are the team-lead, you dispatch to subagents, you
do not write files directly."

This was identified in reflection
`2026-03-19-team-lead-not-dispatching.md`.

### Changes

1. **CLAUDE.md** (inside the CLASI block) -- Add a section that states:
   "When you start a session in this project, you are the team-lead.
   Your role is to dispatch to subagents. You do not write code,
   documentation, or planning artifacts directly. See the team-lead
   agent definition for your full role description."

2. **AGENTS.md** -- Ensure it has an `@CLAUDE.md` reference so agents
   loaded from AGENTS.md also see the CLAUDE.md identity binding.
   Currently CLAUDE.md has `@AGENTS.md` but not the reverse.

## Acceptance Criteria

- [ ] CLAUDE.md contains explicit team-lead identity statement inside the CLASI block
- [ ] The statement says the agent dispatches to subagents and does not write files directly
- [ ] AGENTS.md has an `@CLAUDE.md` reference
- [ ] Existing `@AGENTS.md` reference in CLAUDE.md still works (no circular loading issues)
- [ ] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (this is a documentation/configuration change)
- **Manual verification**: Start a new Claude session in the project and confirm it identifies as team-lead
