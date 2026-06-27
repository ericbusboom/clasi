---
id: '013'
title: Artifact layout reorganization and configurable paths
status: done
branch: sprint/013-artifact-layout-reorganization-and-configurable-paths
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
issues:
- reorganize-clasi-files-visible-clasi-artifacts-docs-documents-src-code-configurable-self-migrating.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 013: Artifact layout reorganization and configurable paths

## Goals

Introduce a configurable path layer into the `Project` class so every artifact
category (issues, sprints, reflections, architecture, design, log, db) resolves
from a central defaults table that can be overridden via `.clasi/config.yaml`.
Make the new visible layout (`clasi/` + `docs/architecture/`) the default for
fresh installs; update agent prompt markdown to match; rebuild the role-guard
hook to derive allow/block sets from live `Project` properties; and deliver a
config-driven detect-and-migrate tool that moves files to their configured
locations on demand.

## Problem

All CLASI artifact paths are hardcoded in `clasi/project.py` and scattered
across `clasi/hook_handlers.py`, `clasi/sprint.py`, and
`clasi/tools/artifact_tools.py`. There is no mechanism for a project to
customize where its artifacts live, no migration path from legacy layouts, and
no way for `clasi init` to self-repair a mis-routed install. Additionally,
agent prompt markdown files hardcode `.clasi/` prefixes that will break once
the default layout changes.

A secondary bug is also in scope: the `is_overview_present` predicate fails on
this repo because `ClasiStateReader.overview_exists()` checks
`project.design_dir / "overview.md"`, but `design_dir` currently returns
`.clasi/design/`, while the file lives at `docs/design/`. The configurable-path
refactor will fix this naturally since `design_dir` will delegate to
`_resolve_dir("design")`.

## Solution

**Phase 1 — Configurable path layer.** Add `ARTIFACT_PATH_DEFAULTS` + 
`_load_paths_config` + `_resolve_dir` to `clasi/project.py`. Rewrite each
category property to delegate to `_resolve_dir`. Add `reflections_dir` and
`db_path`. Route all hardcoded `.clasi.db` / `architecture` / `log` reads in
`hook_handlers.py`, `sprint.py`, and `artifact_tools.py` through `Project`.
Update `init_command.py` to create dirs from the table and write the `paths:`
block to config.yaml.

**Phase 2 — Agent alignment + write-guard.** Update the ~12 plugin prompt
markdown files (plus their `.claude/` mirror copies) that hardcode
`.clasi/{issues,sprints,reflections,architecture}` to the new paths. Rebuild
the role-guard in `hook_handlers.py` to derive allow/block sets from `Project`
properties rather than `clasi_dir` alone.

**Phase 3 — Detect-and-migrate tool.** Generalize `clasi/migrate_command.py`
into config-driven `detect_moves` / `execute_moves`. Wire a `[y/N]` prompt
into `clasi init` (warn-only when non-interactive). Add `--yes/--relocate` to
`init` and `migrate`. Keep the legacy `docs/clasi/` case working.

**Backward-compat safeguard.** Pin this repo's `.clasi/config.yaml` with an
explicit `paths:` block pointing at the current physical locations, so the
running MCP server keeps finding everything after the default-layout change.

## Success Criteria

- `pytest` green; coverage `fail_under` still met.
- `Project(...).issues_dir` returns `clasi/issues` with no `paths:` key;
  returns the override value when one is present.
- `clasi init` in a scratch dir creates `clasi/{issues,sprints,reflections}`,
  `docs/architecture`, `.clasi/{log,config.yaml}` and writes the `paths:` block.
- `clasi status` on THIS repo (with the config-pin ticket applied) still
  resolves all sprints and tickets exactly as today.
- Role-guard allows team-lead writes to `clasi/issues/`, `docs/architecture/`,
  and blocks writes to `clasi/sprints/`.
- `detect_moves` in a scratch repo with files at `.clasi/issues` emits a move
  to `clasi/issues`; `execute_moves` performs the move idempotently.

## Scope

### In Scope

- Phase 1: `ARTIFACT_PATH_DEFAULTS` table, `_load_paths_config`, `_resolve_dir`,
  and category-property delegation in `clasi/project.py`.
- Phase 1: `reflections_dir` property and `db_path` property; `db` property
  uses `db_path`.
- Phase 1: Route `sprint.py`, `artifact_tools.py`, `hook_handlers.py` through
  `Project` properties (no raw `.clasi/...` path construction).
- Phase 1: `init_command.py` iterates `ARTIFACT_PATH_DEFAULTS` to create dirs;
  writes `paths:` block via `setdefault`.
- Phase 1: Fix the overview-presence bug (design_dir now resolves via config).
- Phase 2: Update all plugin prompt markdown + `.claude/` mirror copies.
- Phase 2: Rebuild role-guard allow/block sets from `Project` props.
- Phase 3: `detect_moves` / `execute_moves` in `migrate_command.py`.
- Phase 3: Wire prompt into `clasi init`; `--yes/--relocate` on `init`
  and `migrate`.
- Phase 3: Unit tests for `detect_moves` / `execute_moves` against temp dirs.
- Backward-compat: Pin this repo's `.clasi/config.yaml` paths.

### Out of Scope

- Phase 4: `git mv clasi src/clasi` (source package relocation). Deferred.
- Phase 5: Physically relocating this repo's own `.clasi/` artifacts. Deferred.
- `pyproject.toml` packaging changes (`where=["src"]`). Deferred.
- Any write to `clasi/` or `docs/architecture/` artifact dirs in this repo
  (files remain at `.clasi/` until the deferred finale).

## Test Strategy

- Unit tests for `_load_paths_config` (valid yaml, missing file, wrong type, YAML error).
- Unit tests for `_resolve_dir` (default used when no config; override used when config present).
- Unit tests for `detect_moves` and `execute_moves` against scratch/temp dirs.
- Update `tests/unit/test_migrate_command.py` for changed guard behavior.
- New `tests/unit/test_relocate.py` for Phase 3 logic.
- Role-guard integration: write attempts to allowed and blocked paths.

## Architecture Notes

- `clasi_dir` property keeps its current value (`.clasi`) — it is the hidden
  state anchor (db, log, config). Callers that use `clasi_dir` for DB or log
  must be migrated to `db_path` and `log_dir`.
- `.clasi/` and `.mcp.json` are non-configurable anchors.
- `_load_paths_config` is purely lazy (called once per `Project` instance) and
  swallows all YAML errors gracefully.
- The migration candidate-locations table is static in `migrate_command.py`;
  the destination is always read live from `Project`.

## GitHub Issues

(None — tracked internally via .clasi/issues.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Configurable path layer in Project | — |
| 002 | Route hardcoded paths through Project | 001 |
| 003 | Update init to use path table and write paths block | 001 |
| 004 | Pin this repo's config.yaml paths (backward-compat) | 001 |
| 005 | Rebuild role-guard from Project properties | 001, 002 |
| 006 | Update plugin prompts to new default paths | — |
| 007 | Config-driven detect-and-migrate tool | 001, 002, 003 |
| 008 | Wire migration prompt into clasi init and tests | 007 |

Tickets execute serially in the order listed.
