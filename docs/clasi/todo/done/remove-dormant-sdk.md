---
status: done
sprint: 008
tickets:
- 008-001
---
# Code Review Cleanup: Remove Dormant SDK Dispatch and Align Active Agent Model

## Summary
Create a pending TODO documenting internal cleanup work for CLASI after code review. The cleanup should remove unnecessary Claude SDK usage, delete or retire dead dispatch code, and align docs/tests with the current active model: `team-lead`, `sprint-planner`, and `programmer`.

Target TODO file:
`docs/clasi/todo/code-review-cleanup-remove-dormant-sdk-dispatch-and-align-agent-model.md`

## Key Changes
- Remove the dormant Claude SDK dispatch path entirely.
  - Delete or retire `clasi/tools/dispatch_tools.py`.
  - Remove the misleading `dispatch_tools` import from `clasi/mcp_server.py`.
  - Remove `Agent.dispatch()` SDK behavior from `clasi/agent.py`, preserving only active content-loading/rendering behavior if still needed.
  - Remove `claude-agent-sdk` from `pyproject.toml` once no runtime imports remain.

- Align active agent behavior with the current 3-agent architecture.
  - Stop treating `clasi/plugin/agents/old/*` as active agents.
  - Remove the `Project.get_agent()` fallback into `old`.
  - Update active contracts and instructions that still reference old agents such as `project-manager`, `architect`, `technical-lead`, `sprint-executor`, and `code-reviewer`.

- Clean MCP and process-tool surfaces.
  - Keep dispatch tools unregistered and remove dead registration assumptions.
  - Decide whether commented-out process tools are internal helpers or public MCP tools, then update tests/docs to match the actual surface.

- Refresh stale docs and packaging metadata.
  - Update README and active plugin instructions that still describe old commands, Copilot mirroring, or old agent layout.
  - Remove stale package-data globs for old top-level `agents/`, `skills/`, `instructions/`, and `rules/` paths if unused.

## Test Plan
- Update tests that currently preserve dormant SDK behavior, especially `test_dispatch_tools.py`, `test_agent.py`, and contract tests for old agents.
- Add a guard test confirming normal CLASI runtime paths do not import `claude_agent_sdk`.
- Add content checks preventing old-agent delegation references from reappearing in active plugin prompts/contracts.
- Run the existing unit and system test suite after cleanup.

## Assumptions
- The Claude SDK dispatch path is not required for current CLASI behavior.
- Native Claude/Codex agent or task tooling is the intended sub-agent mechanism going forward.
- Old agents should remain archival only unless a future TODO explicitly restores them.
