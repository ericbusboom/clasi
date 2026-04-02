---
id: '011'
title: Tool returns should be sprint object not dicts
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: tool-returns-should-be-sprint-object-not-dicts.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tool returns should be sprint object not dicts

## Description

MCP tools like `create_sprint` were building hand-constructed dicts for their
JSON return values. The Sprint and Ticket domain objects already have all the
needed properties. Added `to_dict()` methods to both classes and updated the
three tools that built manual dicts (`create_sprint`, `insert_sprint`,
`create_ticket`) to use object serialization instead.

## Acceptance Criteria

- [x] `Sprint.to_dict()` returns a plain JSON-serializable dict with keys: id, path, branch, files, phase
- [x] `Ticket.to_dict()` returns a plain JSON-serializable dict with keys: id, path, title, status
- [x] `create_sprint` uses `sprint.to_dict()` instead of a hand-built dict
- [x] `insert_sprint` uses `sprint.to_dict()` and adds the `renumbered` key
- [x] `create_ticket` uses `ticket.to_dict()` and adds `template_content`
- [x] All existing tests pass (`uv run pytest`)
- [x] New tests for `Sprint.to_dict()` and `Ticket.to_dict()` added

## Testing

- **Existing tests to run**: `uv run pytest tests/system/test_artifact_tools.py tests/unit/test_sprint.py tests/unit/test_ticket.py`
- **New tests to write**: `TestSprintToDict` in test_sprint.py, `TestTicketToDict` in test_ticket.py
- **Verification command**: `uv run pytest`
