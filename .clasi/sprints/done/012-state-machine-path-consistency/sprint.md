---
id: '012'
title: State-machine path consistency
status: done
branch: sprint/012-state-machine-path-consistency
use-cases: []
issues:
- fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md
- gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md
- gh-17-initialize-gate-checks-docs-clasi-overview-md-but-skill-writes-clasi.md
- gh-18-predicates-read-legacy-docs-clasi-bare-id-paths-while-writers-use.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 012: State-machine path consistency

## Goals

Make state-machine predicates resolve artifact paths through the same Project/Sprint
path model the writers use, so tool-created artifacts satisfy their own gates. After
this sprint, a freshly-initiated project transitions state correctly, and `get_status`
reports accurate (not `state_drift`) results for all sprints and tickets.

## Problem

The state-machine predicates hardcode legacy `docs/clasi/` paths with bare sprint/ticket
IDs, while the write side (`clasi/project.py`, `clasi/sprint.py`) and all MCP artifact
tools create artifacts under `.clasi/` with slugged directory and file names. There are
two compounding mismatches:

1. **Root mismatch:** predicates read `docs/clasi/…`; writers write `.clasi/…`.
2. **Name mismatch:** predicates expect bare IDs and `use-cases.md` (hyphenated); writers
   produce `<id>-<slug>` directories, `<id>-<slug>.md` ticket files, and `usecases.md`.

Additionally, `Project.design_dir` returns `docs/design/` (not `.clasi/design/`), and the
`is_overview_present` predicate checks `docs/clasi/overview.md` while the project-initiation
skill writes to `.clasi/design/overview.md`. This permanently blocks the
`uninitialized → planning` transition.

A secondary issue: the sprint state machine does not recognize the `planning-docs` status
the sprint-planner sets (known states: `open, planned, pre-flight, ticketed, executing,
review, closed`) — the planner's `planning_docs` vocabulary is not reconciled with the
machine.

## Solution

1. **Fix `Project.design_dir`** to return `self.clasi_dir / "design"` (`.clasi/design/`).
2. **Add `overview_exists()` to `StateReader`** — derives path from `project.design_dir`
   rather than a hardcoded string; both `ClasiStateReader` and `NullStateReader` implement it.
3. **Fix the overview predicates** (`is_overview_present` / `is_overview_absent`) to call
   `ctx.reader.overview_exists()` instead of `ctx.reader.file_exists("docs/clasi/overview.md")`.
4. **Fix sprint predicates** to resolve sprint dir by ID-prefix match (`<id>-*` glob) rather
   than bare ID, and check `usecases.md` (not `use-cases.md`).
5. **Fix ticket predicates** to resolve ticket files by ID-prefix match (`<id>-*.md`) within
   the slugged sprint directory.
6. **Reconcile `planning-docs` / `planning_docs` status vocabulary** between the sprint-planner
   and the sprint state machine.
7. **Move the clasi repo's own design artifacts** via `git mv` so the repo itself initializes
   cleanly: `docs/design/overview.md` → `.clasi/design/overview.md`, same for
   `specification.md` and `usecases.md`.
8. **Add regression tests** confirming that artifacts created by the write tools satisfy their
   own predicates.

Note: `fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md` contains a confirmed,
detailed implementation plan (including exact code locations and test cases) for facets 1–3 and 7.
This is the primary reference for those facets during detail planning.

Skills source of truth: `clasi/plugin/skills/` — `.claude/` and `.agents/` copies are
installer-generated. Detail planning must target `clasi/plugin/...` for any doc edits.

## Success Criteria

- `pytest tests/unit/test_state_machine/test_predicates.py tests/unit/test_project.py tests/unit/test_status/test_reader.py` passes.
- Full `pytest` suite green with no regressions.
- In a fresh project with `.clasi/design/overview.md` present, `get_status()` returns `planning` (not `uninitialized`).
- In the clasi repo itself (after `git mv`), `get_status()` no longer reports `uninitialized` or `state_drift`.
- Sprint predicate tests confirm artifact presence using `.clasi/sprints/<id>-<slug>/` paths.
- Ticket predicate tests confirm ticket presence using `<id>-<slug>.md` filenames.

## Scope

### In Scope

- `clasi/project.py` — `design_dir` property
- `clasi/status/reader.py` — new `overview_exists()` method
- `clasi/state_machine/context.py` — `StateReader` protocol + `NullStateReader`
- `clasi/state_machine/predicates/project.py` — overview predicates
- `clasi/state_machine/predicates/sprint.py` — sprint artifact predicates (root, slug, filename)
- `clasi/state_machine/predicates/ticket.py` — ticket artifact predicates (root, slug, filename)
- Sprint status vocabulary reconciliation (`planning-docs` / `planning_docs`)
- `git mv` of `.clasi/design/` artifact triad in the clasi repo
- Stale doc/comment references to `docs/clasi/overview.md` in `docs/design/state-machines.md` and `README.md`
- Regression tests for all fixed predicates

### Out of Scope

- Archived agents in `clasi/plugin/agents/old/`
- Legacy `clasi/schemas/se-process/schema.yaml` references (noted only)
- `worktree-process.md` reference in `execute-sprint` (noted only)
- Plan-sprint skill doc edits (addressed in sprint 013)

## Dependencies

NONE. This is the foundational sprint — every later sprint's phase gates depend on this
being fixed. All other sprints in this roadmap (013, 014, 015) should be executed after
this sprint closes.

## Issues Addressed

- `fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md` — contains the confirmed implementation plan for the overview facet; build on it.
- `gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md`
- `gh-17-initialize-gate-checks-docs-clasi-overview-md-but-skill-writes-clasi.md`
- `gh-18-predicates-read-legacy-docs-clasi-bare-id-paths-while-writers-use.md`

## Architecture Notes

The central design principle: predicates must resolve paths through the same `Project` /
`Sprint` model objects the writers use — never hardcoded strings. This makes path
conventions automatically consistent: changing `Project.design_dir` or sprint slug
logic propagates to both writers and readers in one place.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 012-001 | Fix Project.design_dir and add overview_exists to StateReader protocol | — |
| 012-002 | Fix sprint artifact predicates via sprint_artifact_exists protocol method | 012-001 |
| 012-003 | Fix is_ticket_file_present predicate via ticket_file_present protocol method | 012-001 |
| 012-004 | Reconcile planning-docs vocabulary in plugin docs and sprint state machine YAML | 012-001 |
| 012-005 | git mv design artifact triad and update stale doc/skill references to .clasi/design/ | 012-001 |
| 012-006 | Add regression tests confirming predicate/writer path agreement | 012-002, 012-003 |

Tickets execute serially in the order listed.
