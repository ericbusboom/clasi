---
id: '001'
title: Create project-manager agent with initiation and roadmap modes
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: process-redesign-initiation-and-roadmap.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create project-manager agent with initiation and roadmap modes

## Description

Create the project-manager agent with two modes: initiation (processes
written specs into overview.md, specification.md, usecases.md) and
roadmap (groups TODO assessments into sprint roadmaps).

## Acceptance Criteria

- [x] Agent directory created at `clasi/agents/domain-controllers/project-manager/`
- [x] `agent.md` defines both initiation and roadmap modes
- [x] `contract.yaml` validates against contract-schema.yaml
- [x] `dispatch-template.md.j2` has mode-conditional sections
- [x] `Project.get_agent("project-manager")` finds the new agent
- [x] `Project.list_agents()` includes project-manager
- [x] All existing tests continue to pass

## Testing

- **Existing tests to run**: `tests/unit/test_contracts.py`, `tests/unit/test_agent.py`
- **New tests to write**: Added project-manager to ALL_AGENTS parametrized list in test_contracts.py
- **Verification command**: `uv run pytest tests/unit/test_contracts.py tests/unit/test_agent.py`
