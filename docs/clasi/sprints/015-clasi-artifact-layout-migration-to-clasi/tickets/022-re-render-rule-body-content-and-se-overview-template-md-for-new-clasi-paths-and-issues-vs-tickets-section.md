---
id: "022"
title: "Re-render rule body content and se-overview-template for new .clasi/ paths and Issues vs Tickets section"
status: open
use-cases:
  - SUC-001
depends-on:
  - "012"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-render rule body content and se-overview-template for new paths and Issues vs Tickets section

## Description

Update prose-level content that agents and developers read:
1. `clasi/se-overview-template.md` — add an "Issues vs Tickets" section explaining that
   an issue is a proposed change (lives in `.clasi/issues/`) and a ticket is a step within
   a sprint that implements an issue (lives in `.clasi/sprints/<id>/tickets/`). Update
   any `docs/clasi/` path references in body prose.
2. `clasi/plugin/instructions/software-engineering.md` (if it exists) — same updates.
3. Any other template file with `docs/clasi/` body prose that was NOT already handled
   by tickets 009-012.

## Acceptance Criteria

- [ ] `se-overview-template.md` has a clearly-headed "Issues vs Tickets" section
- [ ] Body prose in `se-overview-template.md` references `.clasi/` not `docs/clasi/`
- [ ] `software-engineering.md` (if present) updated similarly
- [ ] No `docs/clasi` prose references in any template file (outside done-sprint archives)
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/se-overview-template.md`
- `clasi/plugin/instructions/software-engineering.md` (if present)
- Any other template prose files with old path references

### Testing plan
- No code tests for prose; verify by grep: `grep -rn "docs/clasi" clasi/*.md clasi/plugin/`
- `uv run pytest` — full suite
