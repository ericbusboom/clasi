---
id: "002"
title: "Add process reminder to document templates"
status: todo
use-cases:
  - SUC-017-002
depends-on: []
---

# Add process reminder to document templates

## Description

Add a single-line HTML comment to each document template reminding
agents to consult the SE process before making changes. The comment
should be placed right after the YAML frontmatter closing `---`.

Reminder line:
```
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->
```

Templates to update:
1. `claude_agent_skills/templates/sprint.md`
2. `claude_agent_skills/templates/sprint-architecture.md`
3. `claude_agent_skills/templates/ticket.md`
4. `claude_agent_skills/templates/sprint-usecases.md`

## Acceptance Criteria

- [ ] sprint.md template contains the reminder after frontmatter
- [ ] sprint-architecture.md template contains the reminder after frontmatter
- [ ] ticket.md template contains the reminder after frontmatter
- [ ] sprint-usecases.md template contains the reminder after frontmatter
- [ ] All existing tests pass

## Testing

- **Existing tests to run**: `uv run pytest` (full suite)
- **New tests to write**: None needed — template content is tested
  implicitly by existing sprint/ticket creation tests.
- **Verification command**: `uv run pytest`
