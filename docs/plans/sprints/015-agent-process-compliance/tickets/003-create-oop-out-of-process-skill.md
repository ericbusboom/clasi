---
id: "003"
title: "Create /oop out-of-process skill"
status: todo
use-cases: [SUC-015-006]
depends-on: []
---

# Create /oop out-of-process skill

## Description

Create a new skill definition `/oop` that lets agents skip all SE ceremony
for small, targeted changes.

**File**: `claude_agent_skills/skills/oop.md` (new)

The skill should instruct the agent to:
- Skip all SE process ceremony (no sprint, no tickets, no gates)
- Read the code, understand the change needed
- Make the change
- Run the test suite
- Commit directly to master with a descriptive message
- Suitable for: typos, small bug fixes, config tweaks, one-line changes

## Acceptance Criteria

- [ ] `claude_agent_skills/skills/oop.md` exists with proper frontmatter
- [ ] Skill appears in `list_skills()` output
- [ ] Skill instructs agent to skip SE ceremony
- [ ] Skill instructs agent to run tests before committing
- [ ] Skill specifies scope: small, targeted changes only

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: None (skill definition is documentation)
- **Verification command**: `uv run pytest`
