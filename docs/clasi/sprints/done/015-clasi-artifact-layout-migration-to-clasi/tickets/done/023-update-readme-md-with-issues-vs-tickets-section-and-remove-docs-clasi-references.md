---
id: "023"
title: "Update README.md with Issues vs Tickets section and remove docs/clasi/ references"
status: done
use-cases:
  - SUC-001
depends-on:
  - "022"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update README.md with Issues vs Tickets section and remove docs/clasi/ references

## Description

Update `README.md` to:
1. Replace all `docs/clasi/` references with `.clasi/` equivalents.
2. Add a clearly-headed "Issues vs Tickets" section that explains:
   - **Issue** — a proposed change to the system. Lives in `.clasi/issues/`.
   - **Ticket** — a step within a sprint implementing an issue. Lives in
     `.clasi/sprints/<id>/tickets/`.
3. Update the directory layout diagram if present.

The rename-todos-to-issues TODO specifies this requirement explicitly.

## Acceptance Criteria

- [x] `README.md` has no `docs/clasi/` references (6 hits at lines 63, 89, 99, 129, 160,
  279 per the TODO)
- [x] README has a clearly-headed "Issues vs Tickets" paragraph
- [x] `grep -n "docs/clasi" README.md` returns zero hits
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `README.md`

### Testing plan
- Grep verification: `grep -rn "docs/clasi" README.md`
- `uv run pytest` — full suite
