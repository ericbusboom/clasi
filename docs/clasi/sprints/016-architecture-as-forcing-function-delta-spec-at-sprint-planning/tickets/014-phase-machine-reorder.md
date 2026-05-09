---
id: "016-014"
title: "Phase-machine: sprint planner authors delta before tickets"
status: todo
use-cases: [SUC-001]
depends-on: ["016-009", "016-010"]
---

# 016-014: Phase-machine — sprint planner authors delta before tickets

## Description

Update the sprint-planner agent prompt and the `plan-sprint` SKILL.md to
enforce the new planning order: architecture-delta is authored between use
cases and tickets, not after. The phase machine in `state_db_class.py` is
UNCHANGED — the existing `planning-docs → architecture-review → ticketing`
sequence already maps correctly to the new order. Only agent prompts and
skills require updating.

## Acceptance Criteria

- [ ] The sprint-planner agent prompt (in `clasi/plugin/agents/`) reflects
  the new planning order:
  1. Sprint overview (sprint.md)
  2. Use cases (usecases.md)
  3. Architecture delta (architecture-delta.md) — this is step 3, before tickets
  4. Tickets
- [ ] The sprint-planner agent prompt explicitly states:
  "Do not create tickets until `architecture-delta.md` exists and
  `validate-delta` returns exit 0."
- [ ] The `plan-sprint` SKILL.md Phase 2 (Detail Mode) process section
  reflects the same order.
- [ ] The sprint-planner agent prompt does NOT reference `architecture-update.md`
  as a valid planning-phase output.
- [ ] `clasi/state_db_class.py` is NOT modified (phase machine unchanged).

## Implementation Plan

### Approach

Locate the sprint-planner agent prompt file. Edit the steps to place
architecture-delta authoring at step 3 (after use cases, before tickets).
Add the explicit "no tickets before validate-delta passes" constraint.
Edit `plan-sprint/SKILL.md` similarly.

### Files to Modify

- Sprint-planner agent prompt file (locate in `clasi/plugin/agents/`)
- `clasi/plugin/skills/plan-sprint/SKILL.md`

### Testing Plan

No automated test. Verify manually that the prompt changes are complete and
unambiguous.

### Documentation Updates

The SKILL.md and agent prompt ARE the documentation.
