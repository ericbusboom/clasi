---
id: "001"
title: "Replace technical-plan template with architecture template"
status: todo
use-cases:
  - SUC-016-001
depends-on: []
---

# Replace technical-plan template with architecture template

## Description

Delete `claude_agent_skills/templates/sprint-technical-plan.md` and create
`claude_agent_skills/templates/sprint-architecture.md` with the standard
architecture document structure plus a `## Sprint Changes` section. Update
`templates.py` to replace `SPRINT_TECHNICAL_PLAN_TEMPLATE` with
`SPRINT_ARCHITECTURE_TEMPLATE`.

## Acceptance Criteria

- [ ] `sprint-technical-plan.md` template deleted
- [ ] `sprint-architecture.md` template created with Sprint Changes section
- [ ] `templates.py` exports `SPRINT_ARCHITECTURE_TEMPLATE`
- [ ] `SPRINT_TECHNICAL_PLAN_TEMPLATE` removed from `templates.py`

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_mcp_server.py`
- **New tests to write**: None (template loading tested implicitly)
- **Verification command**: `uv run pytest`
