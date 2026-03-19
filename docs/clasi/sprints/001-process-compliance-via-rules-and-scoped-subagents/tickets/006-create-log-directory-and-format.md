---
id: "006"
title: "Create log directory structure and format"
status: todo
use-cases: []
depends-on: []
---

# Create log directory structure and format

## Description

Establish the `docs/clasi/log/` directory structure and define the
logging utilities that other tickets will use.

### Directory structure

```
docs/clasi/log/
├── sprints/       # per-sprint subdirectories created on demand
└── adhoc/         # monotonic counter files
```

### Logging utility

Create a small utility (in artifact_tools.py or a new module) that:
- Determines the correct log path given context (sprint name, ticket
  number, or adhoc)
- Computes the next sequence number for the log file
- Writes the log file with YAML frontmatter + full prompt body
- Updates frontmatter with result after dispatch completes

### Log file format

```markdown
---
timestamp: "2026-03-19T14:30:00"
parent: sprint-executor
child: code-monkey
scope: claude_agent_skills/
ticket: "001"
sprint: "001-my-sprint"
result: success
files_modified:
  - claude_agent_skills/foo.py
---

# Dispatch: sprint-executor → code-monkey

<full prompt text>
```

## Acceptance Criteria

- [ ] `docs/clasi/log/` directory structure documented
- [ ] Logging utility creates files with correct frontmatter
- [ ] Sprint log paths: `log/sprints/<name>/sprint-planner-NNN.md`
- [ ] Ticket log paths: `log/sprints/<name>/ticket-NNN-NNN.md`
- [ ] Ad-hoc log paths: `log/adhoc/<N>.md` with monotonic counter
- [ ] Log body contains full prompt text, not summary

## Testing

- **New tests to write**: test log file creation, path routing, sequencing
- **Verification command**: `uv run pytest`
