---
id: '002'
title: Create project-architect agent for TODO assessment
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create project-architect agent for TODO assessment

## Description

Create the project-architect agent in `clasi/agents/task-workers/project-architect/`.
This tier-2 task worker assesses TODOs against the current codebase, producing
impact assessments covering requirements, affected code, difficulty, dependencies,
and change types.

## Acceptance Criteria

- [x] Agent directory exists at `clasi/agents/task-workers/project-architect/`
- [x] `agent.md` defines the project-architect role and workflow
- [x] `contract.yaml` validates against `clasi/contract-schema.yaml`
- [x] `dispatch-template.md.j2` provides dispatch instructions with TODO file paths
- [x] `Project.get_agent("project-architect")` returns a TaskWorker
- [x] `Project.list_agents()` includes project-architect
- [x] All existing tests pass

## Testing

- **Existing tests to run**: `tests/unit/test_agent.py`, `tests/system/test_content_smoke.py`
- **New tests to write**: Contract schema validation, agent discovery, subclass type
- **Verification command**: `uv run pytest`
