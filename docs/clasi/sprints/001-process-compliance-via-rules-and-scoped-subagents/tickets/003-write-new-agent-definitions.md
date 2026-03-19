---
id: "003"
title: "Write new agent definitions"
status: todo
use-cases: []
depends-on: ["001"]
---

# Write new agent definitions

## Description

Create `agent.md` files for the new agents in the hierarchy that don't
have existing definitions. Update existing agents that are being
refactored.

### New agents to create

- `agents/domain-controllers/sprint-planner/agent.md` — extracted from
  project-manager. Owns sprint lifecycle from TODO intake through
  ticket creation. Delegates to architect, architecture-reviewer,
  technical-lead.
- `agents/domain-controllers/sprint-executor/agent.md` — extracted from
  project-manager. Receives sprint + tickets, dispatches code-monkey
  per ticket, validates ticket frontmatter on return, updates sprint
  frontmatter to done.
- `agents/domain-controllers/ad-hoc-executor/agent.md` — formalizes OOP
  pattern. Dispatches code-monkey and code-reviewer for out-of-process
  changes.
- `agents/domain-controllers/todo-worker/agent.md` — manages TODO
  creation, GitHub issue import, TODO lifecycle.
- `agents/domain-controllers/sprint-reviewer/agent.md` — post-sprint
  validation (may extract from close-sprint).

### Agents to refactor

- `main-controller/agent.md` — rewrite project-manager as pure
  dispatcher. Knows requirements → planning → execution flow. Delegates
  everything. Validates sprint frontmatter on return.
- `task-workers/code-monkey/agent.md` — rewrite python-expert as
  language-agnostic ticket implementer. Absorbs documentation-expert
  responsibilities. Gets per-project language instructions.

## Acceptance Criteria

- [ ] 5 new agent.md files created
- [ ] main-controller refactored to pure dispatcher
- [ ] code-monkey written as language-agnostic implementer
- [ ] Each agent.md specifies: role, scope, receives, returns, delegates-to

## Testing

- **Verification command**: `uv run pytest`
