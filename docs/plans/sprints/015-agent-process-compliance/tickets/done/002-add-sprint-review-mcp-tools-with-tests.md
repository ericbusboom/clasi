---
id: '002'
title: Add sprint review MCP tools with tests
status: done
use-cases:
- SUC-015-004
- SUC-015-005
depends-on: []
---

# Add sprint review MCP tools with tests

## Description

Add three new MCP tools to `artifact_tools.py` that validate sprint state at
critical lifecycle checkpoints.

**File**: `claude_agent_skills/artifact_tools.py`

### Tools

1. **`review_sprint_pre_execution(sprint_id)`** — Called before execution.
   Validates: correct branch, sprint directory, planning docs exist with
   non-draft status, real content (not template), tickets exist in todo status.

2. **`review_sprint_pre_close(sprint_id)`** — Called before close_sprint.
   Validates: all tickets done and in tickets/done/, planning docs correct
   status, no template placeholders.

3. **`review_sprint_post_close(sprint_id)`** — Called after close_sprint.
   Validates: tickets finalized, sprint archived to sprints/done/, on master.

### Return Format

```json
{
  "passed": false,
  "issues": [
    {
      "severity": "error",
      "check": "sprint_md_status",
      "message": "sprint.md still has status 'draft'",
      "fix": "Update sprint.md frontmatter status from 'draft' to 'active'",
      "path": "docs/plans/sprints/015-.../sprint.md"
    }
  ]
}
```

### Template Detection

Compare file content (after frontmatter) against templates from
`claude_agent_skills/templates.py`. Create a helper function for this.

## Acceptance Criteria

- [x] `review_sprint_pre_execution` MCP tool exists and returns structured JSON
- [x] `review_sprint_pre_close` MCP tool exists and returns structured JSON
- [x] `review_sprint_post_close` MCP tool exists and returns structured JSON
- [x] Each issue includes severity, check, message, fix, and path fields
- [x] Template placeholder detection works for sprint.md, technical-plan.md, usecases.md
- [x] Unit tests cover happy path (correct sprint passes)
- [x] Unit tests cover missing files, wrong frontmatter, template placeholders
- [x] Unit tests cover ticket state issues (not done, not in done/)
- [ ] Regression tests against historical sprints in sprints/done/

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: `tests/unit/test_sprint_review.py` or
  `tests/system/test_sprint_review.py`
- **Verification command**: `uv run pytest`
