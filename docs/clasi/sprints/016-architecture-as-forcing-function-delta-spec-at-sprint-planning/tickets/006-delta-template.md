---
id: "016-006"
title: "Delta template: clasi/schemas/se-process/delta-template.md"
status: todo
use-cases: [SUC-001]
depends-on: ["016-002"]
issue: delta-specs-for-brownfield-architecture-changes.md
---

# 016-006: Delta template — clasi/schemas/se-process/delta-template.md

## Description

Create the skeleton `architecture-delta.md` template that sprint planners fill
in. This file is the starting point the sprint-planner agent uses when
authoring a new sprint's structural plan. It must make the format
self-documenting — a planner reading it sees the exact structure required
without consulting the format spec separately.

MODIFIED entries describe the change in prose — what changed and why. There
is no round-trippability requirement. The template comments must reflect this:
they should say "describe the change in prose" not "include full updated
content."

## Acceptance Criteria

- [ ] `clasi/schemas/se-process/delta-template.md` exists.
- [ ] The template contains:
  - `## Architecture` top-level heading.
  - All four section headings: `### ADDED Components`,
    `### MODIFIED Components`, `### REMOVED Components`,
    `### RENAMED Components`.
  - One example item under each section (clearly marked as a placeholder).
  - `## Use cases` top-level heading with analogous four sections for
    Scenarios.
  - Inline comments that correctly explain the MODIFIED rule: "Describe the
    change in prose. The reviewer reads this prose. No full-replacement content
    required."
  - Inline comments for RENAMED explaining the `→` separator.
- [ ] The template's inline comments do NOT say "MODIFIED entries must include
  full updated content" — that requirement was dropped.
- [ ] Unused sections may be removed by the planner (the template notes this).
- [ ] The `architecture-authoring` skill (ticket 007) references this file path.

## Implementation Plan

### Approach

Write the template as a Markdown file. Use `<!-- comment -->` syntax for
format rule explanations. Use clearly named placeholder items (e.g.,
`#### Component: ExampleService`) so planners know what to replace.

### Files to Create/Modify

- `clasi/schemas/se-process/delta-template.md` (create)

### Testing Plan

No automated test for the template content itself. Verify visually that the
template structure is valid by running the parser against a lightly-filled
version of it.

### Documentation Updates

None — the template is self-documenting.
