---
id: "007"
title: "Update sprint-roadmap and plan-sprint skill prose"
status: done
use-cases:
  - SUC-005
depends-on:
  - 017-005
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint-roadmap and plan-sprint skill prose

## Description

Two skill files describe the two-phase model but contain prose that is
inconsistent with the (now-implemented) tool behavior. This ticket updates
both to match the actual MCP tool sequence.

**`clasi/plugin/skills/sprint-roadmap/SKILL.md`** — Remove the workaround
steps that previously told agents to delete extra artifacts after `create_sprint`.
The skill now simply describes: call `create_sprint`, receive a roadmap sprint,
write content into `sprint.md`.

**`clasi/plugin/skills/plan-sprint/SKILL.md`** — Phase 1 (Roadmap) section
must state that `create_sprint` produces only `sprint.md` with `status: roadmap`.
Phase 2 (Detail) section must state that the agent calls `detail_sprint(sprint_id)`
before writing planning artifacts; this call scaffolds the missing files and
advances the phase to `planning-docs`.

**Files to modify:**
- `clasi/plugin/skills/sprint-roadmap/SKILL.md`
- `clasi/plugin/skills/plan-sprint/SKILL.md`

## Acceptance Criteria

- [x] `sprint-roadmap/SKILL.md` contains no workaround steps for deleting extra artifacts.
- [x] `sprint-roadmap/SKILL.md` describes the lightweight `create_sprint` flow correctly.
- [x] `plan-sprint/SKILL.md` Phase 1 states `create_sprint` produces only `sprint.md` with `status: roadmap`.
- [x] `plan-sprint/SKILL.md` Phase 2 states `detail_sprint(sprint_id)` is called first to scaffold artifacts.
- [x] No contradictions between the two documents.
- [x] `uv run pytest` passes with no regressions (prose change only, no code touched).

## Implementation Plan

- Read both skill files in full.
- Edit `sprint-roadmap/SKILL.md`: remove the artifact-deletion workaround steps from the Process section.
- Edit `plan-sprint/SKILL.md`:
  - Phase 1 section: update `create_sprint` description to note roadmap-only output.
  - Phase 2 section: add step "Call `detail_sprint(sprint_id)` first; it advances phase to `planning-docs` and scaffolds `usecases.md`, `architecture-update.md`, `tickets/`."

## Testing

- **Existing tests to run**: `uv run pytest` (no test changes; prose only)
- **New tests to write**: None (prose update).
- **Verification command**: `uv run pytest`
