---
id: "010"
title: "Add Codex Support to CLASI Init and Plan Capture"
status: roadmap
branch: sprint/010-add-codex-support-to-clasi-init-and-plan-capture
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010: Add Codex Support to CLASI Init and Plan Capture

## Goals

- Extend `clasi init` with opt-in `--codex` (and `--claude`) flags that install Codex-oriented project files alongside (or instead of) the existing Claude setup.
- Add a `clasi hook codex-plan-to-todo` Stop hook that captures `<proposed_plan>` output from Codex sessions and writes a pending TODO, mirroring the existing `ExitPlanMode` plan-to-todo behavior for Claude.
- Add `clasi uninstall` with platform selection (`--claude`, `--codex`, or both) that removes only CLASI-managed files/sections.

## Scope

### In Scope

- New CLI flags: `clasi init --claude`, `clasi init --codex`, `clasi init --claude --codex`.
- Platform detection (advisory only) and interactive prompt when no flag is supplied.
- Codex init outputs: `AGENTS.md` (CLASI section), `.codex/config.toml`, `.codex/hooks.json`, `.agents/skills/se/SKILL.md`.
- `clasi hook codex-plan-to-todo`: extract `<proposed_plan>`, write TODO, de-dupe by content hash.
- `clasi uninstall --claude`, `clasi uninstall --codex`, `clasi uninstall --claude --codex`.
- TOML read/write dependency (`tomli` + `tomli-w` for Python < 3.11).
- Tests for all new paths, idempotency, and backward compatibility.

### Out of Scope

- Alternative sub-agent dispatch backends (separate TODO if needed).
- Changes to the MCP state machine or sprint lifecycle.
- Anything in `docs/clasi/` planning artifacts (no sprint/ticket schema changes).

## TODO References

Source TODO: `docs/clasi/todo/add-codex-support-to-clasi-init-and-plan-capture.md`

## Sequencing Note

Sprint 010 is the largest sprint of the three and benefits from sprint 008 having removed the dormant SDK dispatch code first — init and hook logic is cleaner when there is no SDK entanglement to navigate around. Sprint 009 is independent and can land before or after 010 without conflict.

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
