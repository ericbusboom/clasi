---
id: '003'
title: Template updates for github-issue field
status: done
use-cases:
- SUC-002
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Template updates for github-issue field

## Description

Update the sprint and ticket templates to support GitHub issue references.

### Implementation

1. **`templates/ticket.md`** — Add `github-issue: ""` to the YAML
   frontmatter (after `depends-on`). Empty string by default; populated
   when created from a TODO with a GitHub issue reference.

2. **`templates/sprint.md`** — Add a `## GitHub Issues` section after
   `## Architecture Notes` and before `## Definition of Ready`:
   ```
   ## GitHub Issues

   (GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)
   ```

### Notes

These are the template files in `claude_agent_skills/templates/`. The
changes affect all *future* sprints and tickets. Existing artifacts are
unaffected.

## Acceptance Criteria

- [x] Ticket template has `github-issue: ""` in frontmatter
- [x] Sprint template has `## GitHub Issues` section
- [x] Existing tests still pass (templates are tested indirectly)

## Testing

- **Existing tests to run**: `uv run pytest` (template changes may affect
  snapshot-style tests)
- **New tests to write**: None needed — template changes are covered by
  existing template loading tests
- **Verification command**: `uv run pytest`
