---
id: "004"
title: "Remove Project.get_agent() fallback into agents/old/"
status: done
use-cases: ["SUC-003"]
depends-on: []
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove Project.get_agent() fallback into agents/old/

## Description

`clasi/project.py` `Project.get_agent()` (lines 173-204) searches
`clasi/plugin/agents/old/` as a fallback when an agent name is not found in the active
directory. This was a transitional shim while old agents were replaced. The active agent
set is now stable (`team-lead`, `sprint-planner`, `programmer`), and the fallback is a
hazard: it can silently serve a stale `old/` definition when a caller passes an outdated
name.

The `old/` directory itself stays on disk as an archive. Only the runtime fallback in
`get_agent()` is removed.

## Acceptance Criteria

- [x] `Project.get_agent()` does not search `clasi/plugin/agents/old/` — the `old_agent_dir` lookup block (project.py lines 193-195) is removed.
- [x] `list_agents()` continues to exclude `old/` (already done via `d.name != "old"` filter; verify no change needed).
- [x] Calling `project.get_agent("architect")` raises `ValueError`.
- [x] The `ValueError` message lists the active agents (`programmer`, `sprint-planner`, `team-lead`).
- [x] `uv run pytest tests/unit/test_project.py` passes.

## Implementation Plan

### Approach

Edit `clasi/project.py`:
1. Remove lines 193-195 (the `old_agent_dir` fallback block: variable declaration,
   `is_dir()` check, and `return Agent(...)` line).
2. Update the `get_agent()` docstring to remove the sentence about `old/` fallback.
3. Verify `list_agents()` already skips `old/` — no change needed there.

### Files to Create / Modify

- **Edit**: `clasi/project.py`

### Testing Plan

- `uv run pytest tests/unit/test_project.py` — existing tests pass.
- Check `tests/unit/test_project.py` for any test asserting old-agent fallback behavior;
  update to assert `ValueError` instead.
- Add a test: `project.get_agent("architect")` raises `ValueError` naming active agents.
- Verify existing test at line 164 of `test_agent.py` ("Non-core agents are in old/ and
  not returned by list_agents") still passes (it already checks `list_agents`, not
  `get_agent`).

### Documentation Updates

`get_agent()` docstring updated inline.
