---
id: "005"
title: "Add Mermaid diagram preference to instructions and skills"
status: todo
use-cases: []
depends-on: []
---

# Add Mermaid diagram preference to instructions and skills

## Description

Add guidance that Mermaid diagrams are preferred over ASCII art for
illustrating system structure, data flow, or component relationships.

**Files**:
- `claude_agent_skills/instructions/software-engineering.md`
- `claude_agent_skills/skills/create-technical-plan.md`
- `claude_agent_skills/skills/elicit-requirements.md`

Add a short note in each: "When illustrating system structure, data flow,
or component relationships, prefer Mermaid diagrams over ASCII art. Mermaid
renders natively in GitHub and most markdown viewers."

## Acceptance Criteria

- [ ] Mermaid preference stated in software-engineering.md
- [ ] Mermaid preference stated in create-technical-plan.md
- [ ] Mermaid preference stated in elicit-requirements.md

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: None (documentation change)
- **Verification command**: `uv run pytest`
