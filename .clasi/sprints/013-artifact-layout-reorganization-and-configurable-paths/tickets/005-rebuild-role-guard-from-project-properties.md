---
id: '005'
title: Rebuild role-guard from Project properties
status: in-progress
use-cases:
- SUC-005
depends-on:
- '001'
- '002'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rebuild role-guard from Project properties

## Description

The role-guard hook in `clasi/hook_handlers.py` (lines ~179–197) currently
allows team-lead (tier 0) writes only under `clasi_dir` (`.clasi/`) and blocks
`sprints_dir` (`.clasi/sprints/`). After tickets 001 and 002, `sprints_dir`
may now resolve to `clasi/sprints/` (the new default) and `issues_dir` resolves
to `clasi/issues/` — neither of which starts with `.clasi/`. The existing guard
would incorrectly block team-lead writes to their own planning dirs.

This ticket rebuilds the allow/block logic to derive all relevant prefixes from
live `Project` properties. The result: the guard is config-aware and requires
no code changes when paths are customized.

## Acceptance Criteria

- [ ] The role-guard allow set for tier 0 is built from `Project` properties:
      `issues_dir`, `reflections_dir`, `architecture_dir`, `design_dir`,
      `clasi_dir`, `log_dir`.
- [ ] The role-guard block set for tier 0 includes `sprints_dir`.
- [ ] The safe-prefix list (`.claude/`, `CLAUDE.md`, `AGENTS.md`) is unchanged.
- [ ] Tier-1 (sprint-planner) may still write under `sprints_dir`.
- [ ] On this repo (with the config pin from ticket 004), a write to
      `.clasi/issues/x.md` is allowed for tier 0 (issues_dir resolves to
      `.clasi/issues`).
- [ ] A write to `.clasi/sprints/013-.../sprint.md` is blocked for tier 0.
- [ ] On a fresh install, a write to `clasi/issues/x.md` is allowed (new
      default).
- [ ] `uv run pytest` passes.

## Implementation Plan

### Files to Modify

- `clasi/hook_handlers.py` — lines ~179–227 (the tier-based allow/block section
  of `handle_pre_tool_use`).

### Implementation Steps

1. After the existing `_proj = get_project()` line, build prefix strings from
   all relevant Project properties:

   ```python
   _proj = get_project()
   def _prefix(p: Path) -> str:
       return str(p.relative_to(_proj.root)) + "/"

   _allow_prefixes = [
       _prefix(_proj.issues_dir),
       _prefix(_proj.reflections_dir),
       _prefix(_proj.architecture_dir),
       _prefix(_proj.design_dir),
       _prefix(_proj.clasi_dir),   # state files: config.yaml, log/, .clasi.db
   ]
   _block_prefixes = [
       _prefix(_proj.sprints_dir),
   ]
   ```

2. Replace the old `_clasi_prefix` / `_sprints_prefix` logic with:

   ```python
   if agent_tier in ("", "0"):
       for blk in _block_prefixes:
           if file_path.startswith(blk):
               # block with existing error message
               ...
       for alw in _allow_prefixes:
           if file_path.startswith(alw):
               _exit_hook("role-guard", payload, 0, "artifact-dir")
   ```

3. Tier-1 check remains: if `agent_tier == "1"` and file_path starts with
   any `_block_prefixes` entry, allow.

4. Ensure the `_prefix()` helper handles the case where the property path is
   NOT relative to `_proj.root` (e.g. if the user configured an absolute path)
   — wrap in a try/except, falling back to the string representation.

### Testing Plan

- Existing hook handler tests in `tests/unit/test_hook_handlers.py` (or similar)
  must pass.
- Add parameterized tests:
  - Allow: `clasi/issues/x.md`, `.clasi/issues/x.md` (depending on config),
    `docs/architecture/x.md`, `.clasi/config.yaml`.
  - Block: `clasi/sprints/013-x/sprint.md`, `src/clasi/project.py`.
  - Use a mock `Project` with configurable `*_dir` properties to test config
    paths without touching the filesystem.

Run: `uv run pytest tests/ -x -v`
