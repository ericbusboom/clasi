---
id: '006'
title: Remove remaining technical-plan references from agents, skills, instructions,
  and rules
status: done
use-cases:
- SUC-016-001
depends-on:
- '004'
---

# Remove remaining technical-plan references from agents, skills, instructions, and rules

## Description

Sprint 016 replaced the separate technical-plan artifact with architecture.md
as a sprint-level document. Tickets 001–005 updated the templates, tools, and
core skills, but many agent definitions, instructions, skills, and rules still
reference "technical plan" or "technical-plan.md". These references need to be
updated to reflect the new architecture-as-sprint-artifact model.

## Files to Update

**Agents:**
- `agents/architect.md` — remove "Sprint Technical Plan" artifact, update modes
- `agents/architecture-reviewer.md` — review architecture.md in sprint dir, not technical-plan.md
- `agents/technical-lead.md` — "technical plans" → "architecture document"
- `agents/project-manager.md` — update delegation map and stage descriptions
- `agents/python-expert.md` — update artifact list
- `agents/documentation-expert.md` — update artifact list
- `agents/requirements-analyst.md` — update artifact list
- `agents/code-reviewer.md` — update artifact list

**Instructions:**
- `instructions/software-engineering.md` — major updates throughout
- `instructions/git-workflow.md` — example commit message

**Skills:**
- `skills/next.md` — "no technical plan" detection
- `skills/project-status.md` — checks for technical-plan.md
- `skills/create-tickets.md` — description and inputs
- `skills/elicit-requirements.md` — legacy file note
- `skills/plan-sprint.md` — remaining prose references

**Rules:**
- `rules/clasi-se-process.md` — stage references

## Acceptance Criteria

- [x] No active content file references "technical-plan.md" as a sprint artifact
- [x] No active content file references "sprint technical plan" as a concept
- [x] Agent descriptions accurately describe the architecture-as-sprint-artifact workflow
- [x] All existing tests pass (298/298)
- [x] `grep -ri "technical.plan" claude_agent_skills/` only matches legacy/historical context

## Testing

- **Existing tests to run**: full suite
- **New tests to write**: none — this is prose-only changes
- **Verification command**: `uv run pytest tests/ -x -o "addopts="`
