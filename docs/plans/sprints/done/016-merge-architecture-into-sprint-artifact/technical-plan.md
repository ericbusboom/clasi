---
status: approved
from-architecture-version: null
to-architecture-version: null
---

# Sprint 016 Technical Plan

## Architecture Version

- **From version**: N/A (no architecture versions exist yet for CLASI itself)
- **To version**: no change (this is a process/tooling change)

## Architecture Overview

This sprint modifies the CLASI tooling to treat `architecture.md` as a
sprint-level artifact instead of maintaining a separate `technical-plan.md`.
The main changes are in `artifact_tools.py`, `templates.py`, and the
skill/instruction/agent markdown files.

## Component Design

### Component: Template System (`templates.py` + `templates/`)

**Use Cases**: SUC-016-001

Remove `SPRINT_TECHNICAL_PLAN_TEMPLATE` and `sprint-technical-plan.md`.
Add `SPRINT_ARCHITECTURE_TEMPLATE` and `sprint-architecture.md` template
with a `## Sprint Changes` section.

### Component: Sprint Creation (`artifact_tools.py::create_sprint`)

**Use Cases**: SUC-016-001

Modify to copy previous architecture doc from `docs/plans/architecture/`
into the new sprint directory as `architecture.md`. Fall back to template
if none exists. Stop creating `technical-plan.md`.

### Component: Sprint Review Tools (`artifact_tools.py::review_sprint_*`)

**Use Cases**: SUC-016-002

Replace all `technical-plan.md` references with `architecture.md` in the
three review functions.

### Component: Skills and Instructions (markdown files)

**Use Cases**: SUC-016-001, SUC-016-002, SUC-016-003

Update `plan-sprint.md`, `close-sprint.md`, `agents-section.md`,
`architectural-quality.md`, `architect.md`, `architecture-reviewer.md`.
Delete `create-technical-plan.md`.
