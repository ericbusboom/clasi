---
id: '007'
title: Expand agent.py file header
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: expand-agent-py-file-header.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Expand agent.py file header

## Description

The module docstring for `clasi/agent.py` was minimal. This ticket expands
it to describe the class hierarchy (Agent, MainController, DomainController,
TaskWorker), the dispatch lifecycle, and how agents relate to contracts and
templates.

## Acceptance Criteria

- [x] The module docstring in `clasi/agent.py` describes the class hierarchy
      (Agent, MainController, DomainController, TaskWorker) and what each
      tier means.
- [x] The module docstring describes how agents relate to contracts
      (contract.yaml) and templates (dispatch-template.md.j2).
- [x] The module docstring describes the seven-step dispatch lifecycle
      implemented in `Agent.dispatch()`.
- [x] All existing tests pass.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: No new tests required — this is a documentation-only change.
- **Verification command**: `uv run pytest`
