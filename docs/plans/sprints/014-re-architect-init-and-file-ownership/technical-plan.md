---
status: draft
---

# Sprint 014 Technical Plan

## Architecture Overview

This sprint adds content files and updates existing ones. No MCP server code
changes are needed because the server already auto-discovers content in the
agents/, instructions/, and skills/ directories.

Components affected:
- `instructions/` — New file: `architectural-quality.md`
- `agents/` — Replace: `architect.md`, `architecture-reviewer.md`
- `instructions/software-engineering.md` — Update references
- `templates.py` — Update sprint technical plan template
- `docs/plans/architecture/` — New directory with baseline document

## Component Design

### Component: Architectural Quality Instruction

**Use Cases**: SUC-001, SUC-002

New instruction file at `claude_agent_skills/instructions/architectural-quality.md`.
Source content from `docs/plans/todo/done/add-versioned-architecture-process/architectural-quality.md`.
Defines versioning rules, core principles (cohesion, coupling, boundaries,
abstraction, dependency direction), document structure, dependency mapping,
interface design, design rationale format, and anti-patterns.

### Component: Versioned Architect Agent

**Use Cases**: SUC-001

Replace `claude_agent_skills/agents/architect.md` with content from
`docs/plans/todo/done/add-versioned-architecture-process/architect.md`.
Key changes: two modes of work (initial + sprint update), 7-step process,
references architectural-quality.md, produces versioned architecture docs.

### Component: Expanded Architecture Reviewer Agent

**Use Cases**: SUC-002

Replace `claude_agent_skills/agents/architecture-reviewer.md` with content from
`docs/plans/todo/done/add-versioned-architecture-process/architecture-reviewer.md`.
Key changes: 7 review criteria (version consistency, codebase alignment, design
quality, anti-patterns, risks, missing considerations, design rationale),
Design Quality Assessment in every review, expanded verdict guidelines.

### Component: Software Engineering Instructions Update

**Use Cases**: SUC-003

Update `claude_agent_skills/instructions/software-engineering.md` to:
- Add `architectural-quality.md` to the instruction list
- Reference `docs/plans/architecture/` in the directory layout
- Update architect agent description to mention versioned output
- Update architecture-reviewer description to mention quality assessment
- Note that sprint planning includes architecture version production
- Note that not every sprint requires a new architecture version

### Component: Sprint Template Update

**Use Cases**: SUC-003

Update `SPRINT_TECHNICAL_PLAN_TEMPLATE` in `claude_agent_skills/templates.py`
to include "From architecture version" and "To architecture version" fields.

### Component: Architecture Baseline Document

**Use Cases**: SUC-001

Create `docs/plans/architecture/architecture-001.md` describing the current
system as-is. This is produced by analyzing the existing codebase and
documentation, following the document structure defined in
`architectural-quality.md`.
