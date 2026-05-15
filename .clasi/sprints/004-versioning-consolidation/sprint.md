---
id: '004'
title: Versioning Consolidation
status: planning-docs
branch: sprint/004-versioning-consolidation
use-cases: []
issues:
- consolidate-clasi-version-storage.md
- migrate-clasi-versioning-to-depend-on-dotconfig.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 004: Versioning Consolidation

## Goal

Stop maintaining two independent forks of the same versioning logic. `clasi/versioning.py` (~500 lines) and `dotconfig/versioning.py` are clearly forks of each other and have already started diverging silently. This sprint adds `dotconfig` as a runtime dependency of `clasi`, shrinks `clasi/versioning.py` to a thin clasi-specific shim (~50 lines) that re-exports from `dotconfig.versioning`, and eliminates the standalone `.agents/.clasi-version` file in favor of the version stored by dotconfig as the single canonical source. Both issues land together because they share the same dotconfig dependency decision and the same version-source authority question.

The chosen implementation path is Option 2 (thin shim): `clasi.yaml` keeps `load_version_trigger` and `should_version` as clasi-specific logic, while all shared computation (`compute_next_version`, `update_version_file`, `create_version_tag`, etc.) delegates to `dotconfig.versioning`.

## Issues in scope

- `issues/consolidate-clasi-version-storage.md` — eliminate `.agents/.clasi-version`; dotconfig is the single source of truth for the CLASI version. Decision recorded in the issue: Option 2.
- `issues/migrate-clasi-versioning-to-depend-on-dotconfig.md` — add `dotconfig` as a runtime dependency, reduce `clasi/versioning.py` to a thin shim re-exporting from `dotconfig.versioning`, update tests and MCP hot-reload list.

## Out of scope

- Removing `clasi/versioning.py` entirely — the shim still needs a home for `close_sprint`'s bridge logic.
- Changing `close_sprint` to shell out to `dotconfig version bump` — different design decision, its own issue.
- Retiring `docs/versioning.md` — can be rewritten after this lands, not in scope here.
- Moving clasi-specific trigger config (`version_trigger`, `should_version`) into dotconfig — that would require changes to dotconfig and is Option 1 territory.

## Notes / open questions

- **Config file authority**: Which config file wins when both `.clasi/config.yaml` and `config/dotconfig.yaml` are present? Option 2 says `.clasi/config.yaml` wins for clasi-specific triggers; `config/dotconfig.yaml` is the source for everything dotconfig handles. The bridge (`config_dir=` argument or a fallback) needs to be designed during detail planning.
- **dotconfig version pin**: The pinned version of dotconfig to use must be determined at detail time. It should be the same version already installed in this project (check `pyproject.toml` and `uv.lock`).

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Add dotconfig as runtime dependency and verify import surface | — |
| 002 | Shrink clasi/versioning.py to thin shim re-exporting from dotconfig | 001 |
| 003 | Eliminate .agents/.clasi-version — verify no write path remains, update docs | 001 |
| 004 | Migrate tests/unit/test_versioning.py — rewrite against shim | 002 |
| 005 | Update MCP hot-reload list and verify close_sprint end-to-end JSON shape | 002, 004 |

Tickets execute serially in the order listed. Tickets 002 and 003 both depend on
001 only; they may be executed in either order. Ticket 005 is the final integration
gate and must follow both 002 and 004.
