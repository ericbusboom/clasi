---
id: "006"
title: "Lift se-process skill prose into instructions/*.md files"
status: done
use-cases: [SUC-004]
depends-on: ["005"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Lift se-process skill prose into instructions/*.md files

## Description

Extract the instructional prose from five skill `SKILL.md` files into the
corresponding `clasi/schemas/se-process/instructions/*.md` files created as
stubs in ticket 005.

The five skills are: `plan-sprint`, `execute-sprint`, `architecture-review`,
`sprint-review`, `close-sprint`. The prose is moved verbatim — no content
changes, no rewriting. After this ticket, the instruction files contain the
full prose that was previously embedded inline.

The `SKILL.md` files themselves are NOT changed in this ticket. That is
ticket 007. This ticket is purely a prose migration — copy content to the
right destination files.

## Acceptance Criteria

- [x] `se-process/instructions/sprint-plan.md` contains the full instructional prose from `plan-sprint/SKILL.md` (excluding the YAML frontmatter and skill-loader scaffolding).
- [x] `se-process/instructions/execution.md` contains the full instructional prose from `execute-sprint/SKILL.md`.
- [x] `se-process/instructions/architecture-update.md` contains the full instructional prose from `architecture-review/SKILL.md`.
- [x] `se-process/instructions/close.md` contains the full instructional prose from `close-sprint/SKILL.md`.
- [x] A `sprint-review.md` instruction file is created and populated from `sprint-review/SKILL.md` prose (even if `sprint-review` is not a schema artifact, the prose is preserved for reference).
- [x] The instruction files do not contain any YAML frontmatter or skill-specific loader scaffolding — just the instructional markdown.
- [x] `uv run pytest` passes (no behavioral changes in this ticket).

## Implementation Plan

**Approach**: Read each `SKILL.md`, identify the instructional prose section
(below the frontmatter and any loader scaffolding), and write it to the
corresponding instruction file. The mapping is:

| Skill | Instruction file |
|-------|-----------------|
| `plan-sprint/SKILL.md` | `se-process/instructions/sprint-plan.md` |
| `execute-sprint/SKILL.md` | `se-process/instructions/execution.md` |
| `architecture-review/SKILL.md` | `se-process/instructions/architecture-update.md` |
| `sprint-review/SKILL.md` | `se-process/instructions/sprint-review.md` (new) |
| `close-sprint/SKILL.md` | `se-process/instructions/close.md` |

**Files to modify**:
- `clasi/schemas/se-process/instructions/sprint-plan.md` — replace stub
- `clasi/schemas/se-process/instructions/execution.md` — replace stub
- `clasi/schemas/se-process/instructions/architecture-update.md` — replace stub
- `clasi/schemas/se-process/instructions/close.md` — replace stub

**Files to create**:
- `clasi/schemas/se-process/instructions/sprint-review.md`

**Testing plan**: No new tests. Verify prose is intact by reading the resulting files.

**Documentation updates**: None.
