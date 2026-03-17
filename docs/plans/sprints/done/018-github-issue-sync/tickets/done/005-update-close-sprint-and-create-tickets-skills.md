---
id: '005'
title: Update close-sprint and create-tickets skills
status: done
use-cases:
- SUC-002
- SUC-003
depends-on:
- '002'
- '003'
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update close-sprint and create-tickets skills

## Description

Update two existing skill definitions to handle GitHub issue references
throughout the sprint lifecycle.

### Implementation

1. **`skills/close-sprint.md`** — Add a new step between step 5 (run
   final validation) and step 6 (merge sprint branch):

   **Close linked GitHub issues**: Read the sprint doc's `## GitHub
   Issues` section. For each `owner/repo#N` reference, call the
   `close_github_issue` MCP tool. If closing fails for any issue, log
   the failure but continue. Include a summary of closed issues in
   step 12 (report completion).

2. **`skills/create-tickets.md`** — Add guidance to the process:

   When creating tickets from TODOs that have a `github-issue` field in
   their frontmatter, copy the `github-issue` value to the new ticket's
   frontmatter. After all tickets are created, collect all `github-issue`
   references and list them in the sprint doc's `## GitHub Issues`
   section.

## Acceptance Criteria

- [ ] `close-sprint` skill has GitHub issue closing step
- [ ] `close-sprint` step specifies best-effort (failures don't block)
- [ ] `close-sprint` completion summary includes closed issues
- [ ] `create-tickets` skill instructs propagation of `github-issue` from TODO to ticket
- [ ] `create-tickets` skill instructs populating sprint doc's `## GitHub Issues` section

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_process_tools.py`
- **New tests to write**: None — skill definitions are static markdown
- **Verification command**: `uv run pytest`
