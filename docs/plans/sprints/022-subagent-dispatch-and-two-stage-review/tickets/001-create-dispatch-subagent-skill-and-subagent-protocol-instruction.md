---
id: "001"
title: "Create dispatch-subagent skill and subagent-protocol instruction"
status: todo
use-cases: [SUC-001, SUC-003]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create dispatch-subagent skill and subagent-protocol instruction

## Description

Create two new content files that define how CLASI agents dispatch work
to isolated subagents:

1. **skills/dispatch-subagent.md** — Defines the controller/worker
   pattern. The controller agent reads the ticket plan, curates context
   (only the files, specs, and constraints the subagent needs), composes
   a prompt, dispatches a fresh Claude Code subagent via the Agent tool,
   reviews the results, and iterates with feedback if needed. The
   controller never writes code directly — all implementation is
   delegated to the subagent.

2. **instructions/subagent-protocol.md** — Defines the include/exclude
   rules for context curation. Include: relevant source files, ticket
   description, acceptance criteria, applicable architecture decisions,
   coding standards, testing instructions. Exclude: conversation history,
   other tickets, debugging logs, full directory listings, sprint-level
   planning docs not relevant to the task.

MUST read Superpowers `subagent-driven-development.md` at
github.com/obra/superpowers for details on the controller/worker pattern,
context curation best practices, and subagent lifecycle management.

## Acceptance Criteria

- [ ] `skills/dispatch-subagent.md` exists and defines the controller/worker dispatch pattern
- [ ] `instructions/subagent-protocol.md` exists and defines context include/exclude rules
- [ ] Context curation rules are specific and actionable (not vague guidance)
- [ ] Controller is explicitly prohibited from writing code directly
- [ ] Dispatch skill references the subagent-protocol instruction
- [ ] Iteration loop (dispatch, review, feedback, re-dispatch) is defined

## Testing

- **Existing tests to run**: `uv run pytest` — skill listing and instruction listing tests must pick up the new files
- **New tests to write**: None required (content-only files, discovered by existing listing tests)
- **Verification command**: `uv run pytest`
