---
id: "004"
title: "Update skills, instructions, and agents-section"
status: todo
use-cases:
  - SUC-016-001
  - SUC-016-002
  - SUC-016-003
depends-on: []
---

# Update skills, instructions, and agents-section

## Description

Update all markdown skill, instruction, and agent files:

1. **`skills/plan-sprint.md`** — Replace `technical-plan.md` refs with
   `architecture.md`. Update step 3 output. Add architecture update steps.
2. **`skills/create-technical-plan.md`** — Delete.
3. **`skills/close-sprint.md`** — Add architecture versioning steps (copy
   to `docs/plans/architecture/architecture-NNN.md`, move old to done/).
4. **`init/agents-section.md`** + **`AGENTS.md`** — Replace `technical-plan.md`
   in sprint lifecycle.
5. **`instructions/architectural-quality.md`** — Rewrite "Architecture as a
   Living Document" for sprint-local workflow with version = sprint number.

## Acceptance Criteria

- [ ] `plan-sprint.md` references `architecture.md` not `technical-plan.md`
- [ ] `create-technical-plan.md` deleted
- [ ] `close-sprint.md` includes architecture versioning steps
- [ ] `agents-section.md` and `AGENTS.md` updated
- [ ] `architectural-quality.md` describes sprint-local workflow
- [ ] No remaining references to `technical-plan` in skills/instructions

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_init_command.py`
- **New tests to write**: None
- **Verification command**: `uv run pytest`
