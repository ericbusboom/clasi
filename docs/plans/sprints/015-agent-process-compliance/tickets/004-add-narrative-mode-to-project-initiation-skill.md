---
id: "004"
title: "Add narrative mode to project-initiation skill"
status: todo
use-cases: [SUC-015-007]
depends-on: []
---

# Add narrative mode to project-initiation skill

## Description

Update the `project-initiation` skill to offer a narrative mode option early
in the interview.

**File**: `claude_agent_skills/skills/project-initiation.md`

Add a step where the agent presents options via AskUserQuestion:
- "Answer structured questions" (current behavior)
- "Start an open narrative"

If narrative mode is chosen:
1. Agent listens to free-form stakeholder input
2. Agent synthesizes the narrative into structured documents
3. Agent follows up with clarifying questions for any gaps

## Acceptance Criteria

- [ ] project-initiation skill offers narrative mode option via AskUserQuestion
- [ ] Narrative mode instructions tell agent to listen, synthesize, then clarify
- [ ] Structured question path still works as before

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: None (skill definition is documentation)
- **Verification command**: `uv run pytest`
