---
id: '007'
title: Move non-core agents to clasi/plugin/agents/old/
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: move-extra-agents-to-old.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Move non-core agents to clasi/plugin/agents/old/

## Description

Sprint 003 ticket 005 moved all 13 agents from `clasi/agents/` into
`clasi/plugin/agents/` as a flat list. Only 3 are actively used: **team-lead**,
**sprint-planner**, and **programmer**. The other 10 (ad-hoc-executor, architect,
architecture-reviewer, code-reviewer, project-architect, project-manager,
sprint-executor, sprint-reviewer, technical-lead, todo-worker) are legacy and
should be clearly separated.

Move the 10 non-core agents into `clasi/plugin/agents/old/` so they are preserved
but not treated as active. Update `project.list_agents()` to skip the `old/`
subdirectory so only the 3 active agents are returned. The `contracts.py`
`_find_contract_path()` function already uses `rglob` and will continue to search
`old/` without changes — verify this is true and leave it as-is. Update any tests
that assert agent names or counts that would break after the move.

## Acceptance Criteria

- [x] The 10 non-core agents (ad-hoc-executor, architect, architecture-reviewer,
      code-reviewer, project-architect, project-manager, sprint-executor,
      sprint-reviewer, technical-lead, todo-worker) are moved to
      `clasi/plugin/agents/old/`
- [x] `team-lead`, `sprint-planner`, and `programmer` remain at the top level of
      `clasi/plugin/agents/`
- [x] `project.list_agents()` returns only the 3 active agents (skips `old/`
      subdirectory)
- [x] `contracts.load_contract()` still finds contracts for all agents including
      those in `old/` (no change needed — `_find_contract_path` already uses
      `rglob`)
- [x] `uv run pytest` passes with no failures

## Implementation Plan

### Approach

1. Move the 10 agent directories into `clasi/plugin/agents/old/`. The `old/`
   directory already exists and is empty.
2. Update `project.list_agents()` in `clasi/project.py` to filter out the `old`
   subdirectory when iterating `agents_dir`.
3. Verify `contracts.py` `_find_contract_path` — it already uses `agents_dir.rglob`
   which recurses into `old/`, so no change is needed there.
4. Verify `process_tools.py` `_list_agents_recursive` — it also uses `rglob` for
   finding `agent.md` files; update it to skip entries whose path includes `old/`
   so `list_agents()` MCP tool also returns only active agents.
5. Update `tests/unit/test_agent.py`: the `test_list_agents_returns_all` test
   currently asserts `"architect" in names` — remove that assertion (architect
   moves to `old/`). The `test_list_agents_includes_all_tiers` test asserts
   `tiers == {0, 1, 2}` — verify whether tiers still span 0-2 after the move or
   update accordingly.

### Files to Modify

- `clasi/plugin/agents/` — move 10 agent directories into `old/` subdirectory
- `clasi/project.py` — `list_agents()`: add check to skip `agent_dir` if its name
  is `old` (i.e., `if agent_dir.name == "old": continue`)
- `clasi/tools/process_tools.py` — `_list_agents_recursive()`: filter out paths
  under `old/` subdirectory
- `tests/unit/test_agent.py` — update assertions that reference non-core agents
  or tier counts

### Testing Plan

- Run `uv run pytest` after changes and confirm all tests pass.
- Spot-check: `project.list_agents()` returns exactly team-lead, sprint-planner,
  programmer.
- Spot-check: `contracts.load_contract("architect")` still succeeds (finds file
  in `old/`).

### Documentation Updates

None required.
