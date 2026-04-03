---
id: '005'
title: Consolidate clasi/ content dirs into clasi/plugin/
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: consolidate-clasi-dirs-into-plugin.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Consolidate clasi/ content dirs into clasi/plugin/

## Description

Sprint 003 moved `plugin/` into `clasi/plugin/`, but several parallel directories
inside `clasi/` still duplicate or overlap with plugin content. This ticket completes
the consolidation by moving all remaining content directories into `clasi/plugin/`
and updating all Python references. After this work, the only subdirectories inside
`clasi/` should be `clasi/plugin/`, `clasi/templates/`, `clasi/tools/`, and
standard Python module files.

Directories to address:

- `clasi/rules/` — markdown files with no Python refs; audit for unique content,
  move anything worth keeping to `clasi/plugin/rules/`, then delete.
- `clasi/skills/` — older skill content overlapping with `clasi/plugin/skills/`;
  move unique files, discard overlaps, then delete.
- `clasi/hooks/` — `role_guard.py` is identical to `clasi/plugin/hooks/role_guard.py`;
  update `test_role_guard.py` to reference `clasi/plugin/hooks/`, update
  `pyproject.toml` coverage omit list, then delete `clasi/hooks/`.
- `clasi/agents/` — 13 agent dirs with `contract.yaml` used by `contracts.py`;
  move into `clasi/plugin/agents/` (merging with existing 3 agents), update
  `contracts.py` line 44 to search `clasi/plugin/agents/`, update
  `project.py` `_agents_dir` property, update any references in
  `process_tools.py`, then delete `clasi/agents/`.

## Acceptance Criteria

- [x] `clasi/rules/` files moved to `clasi/plugin/rules/`, original directory deleted
- [x] `clasi/skills/` unique files moved to `clasi/plugin/skills/`, overlaps discarded, original directory deleted
- [x] `clasi/hooks/` deleted; `tests/unit/test_role_guard.py` updated to reference `clasi/plugin/hooks/role_guard.py`; `pyproject.toml` coverage omit entry updated
- [x] All 13 agent dirs from `clasi/agents/` moved into `clasi/plugin/agents/`, merging with the existing 3 agents; `clasi/agents/` deleted
- [x] `clasi/contracts.py` line 44 updated to `_CONTENT_ROOT / "plugin" / "agents"`
- [x] `clasi/project.py` `_agents_dir` property updated to `clasi/plugin/agents/`
- [x] Any agent dir references in `clasi/tools/process_tools.py` updated
- [x] `uv run pytest` passes with no failures
- [x] Directories `clasi/agents/`, `clasi/hooks/`, `clasi/rules/`, `clasi/skills/` no longer exist

## Implementation Plan

### Approach

Work directory by directory, starting with the ones that have no Python references
(rules, skills), then hooks (one test update), and finishing with agents (the most
involved: code changes in contracts.py, project.py, process_tools.py).

### Files to Create or Modify

- `clasi/contracts.py` — update agents search path (line ~44)
- `clasi/project.py` — update `_agents_dir` property
- `clasi/tools/process_tools.py` — update any agent dir references
- `tests/unit/test_role_guard.py` — update import/path to `clasi/plugin/hooks/`
- `pyproject.toml` — update coverage `omit` list (remove `clasi/hooks/*` entry)
- Move/delete file tree operations for the four content directories

### Testing Plan

- Run `uv run pytest` after each directory is removed to catch breakage early.
- Confirm the four directories no longer exist with a directory listing check.
- Verify agent contract loading still works by running the full test suite.

### Documentation Updates

No documentation changes needed beyond the code references above.
