---
id: "{id}"
title: "{title}"
status: open
use-cases: []
depends-on: []
github-issue: ""
issue: ""
# completes_issue: Controls whether linked issues are archived when this ticket
# is moved to done. Default: true (archive when all referencing tickets are done).
# Set to false (scalar) to suppress archival for ALL linked issues on this ticket.
# Set to a mapping {{filename.md: false}} to suppress archival per issue filename.
# Use false for tickets that partially address a multi-sprint umbrella issue.
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# {title}

## Description

(What needs to be done and why.)

## Acceptance Criteria

- [ ] (Criterion)

## Testing

- **Existing tests to run**: (list test files/commands to verify no regressions)
- **New tests to write**: (describe tests that validate this ticket's changes)
- **Verification command**: `uv run pytest`
