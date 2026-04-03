---
id: '001'
title: Move plugin/ into clasi/plugin/ package data
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo: consolidate-agent-definitions-and-skills.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Move plugin/ into clasi/plugin/ package data

## Description

The `plugin/` directory at the repo root contains installable Claude Code content
(3 agents, 27 skills, hooks) that `clasi init` copies into target projects. This
directory is not proper Python package structure — it cannot be reliably bundled as
package data without fragile relative-path hacks in `init_command.py`.

Move `plugin/` to `clasi/plugin/` (inside the Python package), update `_PLUGIN_DIR`
in `init_command.py` to resolve from the package-internal path, update `pyproject.toml`
to include `plugin/**/*` as package data, and remove the old `plugin/` directory.

The `clasi/agents/` hierarchy is **not** touched — it serves a different purpose
(contract validation via `contracts.py`) and is not part of this consolidation.

## Acceptance Criteria

- [x] `clasi/plugin/` exists and contains all content previously in `plugin/`
      (agents/, skills/, hooks/ subdirectories with identical file contents)
- [x] `plugin/` at the repo root no longer exists
- [x] `_PLUGIN_DIR` in `clasi/init_command.py` resolves to `Path(__file__).parent / "plugin"`
      (i.e., `clasi/plugin/`); the old `parent.parent / "plugin"` dev fallback is removed
- [x] `pyproject.toml` `[tool.setuptools.package-data]` includes `"plugin/**/*"` under
      the `clasi` key
- [x] `uv run pytest` passes (no test references the old `plugin/` path)
- [x] `clasi init` run against a test directory produces the same `.claude/` output as before
- [x] Any documentation or script references to the old `plugin/` path are updated

## Implementation Plan

### Approach

1. Copy `plugin/` to `clasi/plugin/` preserving directory structure.
2. Update `clasi/init_command.py`: simplify `_PLUGIN_DIR` to
   `Path(__file__).parent / "plugin"` (remove the conditional fallback).
3. Update `pyproject.toml`: add `"plugin/**/*"` to `[tool.setuptools.package-data]`
   under `clasi`. Remove any root-level `plugin/` reference if present.
4. Grep repo for remaining references to `plugin/` at the root level and update them
   (README, CI scripts, etc.).
5. Delete `plugin/` from the repo root.
6. Run `uv run pytest` to confirm no regressions.

### Files to Create

- `clasi/plugin/` — directory tree (copy of `plugin/`)
  - `clasi/plugin/agents/programmer/agent.md`
  - `clasi/plugin/agents/sprint-planner/agent.md`
  - `clasi/plugin/agents/team-lead/agent.md`
  - `clasi/plugin/skills/*/SKILL.md` (27 skill files)
  - `clasi/plugin/hooks/hooks.json`
  - `clasi/plugin/hooks/*.py`

### Files to Modify

- `clasi/init_command.py` — update `_PLUGIN_DIR` assignment
- `pyproject.toml` — update `[tool.setuptools.package-data]`
- Any files referencing the old `plugin/` root path (check with `grep -r "plugin/"`)

### Files to Delete

- `plugin/` (entire directory tree at repo root)

### Testing Plan

- Run `uv run pytest` after file moves to catch any test path references.
- Manual smoke test: `python -c "from clasi.init_command import _PLUGIN_DIR; print(_PLUGIN_DIR); assert _PLUGIN_DIR.exists()"`.
- If an integration test for `clasi init` exists, run it to verify installed output.

### Documentation Updates

- Check `README.md` and any docs referencing `plugin/` and update paths.
