---
id: 016-002
title: 'architecture-authoring skill: forward-looking prose framing'
status: done
use-cases:
- SUC-001
depends-on: []
todos:
- sprint-process-changes.md
---

# 016-002: architecture-authoring skill — forward-looking prose framing

## Description

Fix the Mode 2 opening in `clasi/plugin/skills/architecture-authoring/SKILL.md`
so it frames the sprint architecture-update as a forward-looking planning
document, not a retrospective diff.

**Verification finding**: The current Mode 2 text opens with:
> "Write a focused architecture diff describing what changed in this sprint."

The phrase "what changed" implies the architect is recording changes that have
already been decided. This is backward: the artifact is authored *before*
tickets exist, and tickets are derived from it. The fix is a targeted prose
edit to the Mode 2 opening paragraph.

The 7-step methodology below the opening is correct and stays unchanged. The
quality checks stay unchanged. Only the Mode 2 introductory framing is edited.

**Also confirmed clean (no changes needed)**:
- The `architecture-review/SKILL.md` has no parser, no format check, no
  validate-delta reference — it is already a pure prose review. No edits.
- The sprint-planner agent prompt already places Phase 2 (Architecture) before
  Phase 4 (Ticket Creation) with inline Phase 3 review. No edits.
- `state_db_class.py` phase machine is already correct. No edits.

## Acceptance Criteria

- [x] `architecture-authoring/SKILL.md` Mode 2 opening does NOT use the phrase
  "what changed" or any retrospective framing ("what was implemented",
  "record of changes", "diff of what occurred").
- [x] Mode 2 explicitly states the artifact is authored before tickets exist.
- [x] Mode 2 states the guiding question: "Is this description clear enough
  that tickets can be derived from it without ambiguity?"
- [x] Mode 2 describes the artifact's dual role: structural plan at authoring
  time, historical record (ADR at sprint granularity) after the sprint closes.
- [x] No reference to a parser, validator, delta format, or CLI subcommand
  appears anywhere in the SKILL.md.
- [x] The artifact name remains `architecture-update.md` (not renamed).
- [x] The 7-step methodology and quality checks are unchanged.

## Implementation Plan

### Approach

Read the current `architecture-authoring/SKILL.md`. Rewrite the Mode 2
opening paragraph only. The steps below it (1–7) and the Quality Checks
section are not touched.

The new Mode 2 opening should convey:
- This is a planning document, not a retrospective record.
- It is authored after use cases and before tickets.
- Its purpose is to describe the architectural change clearly enough that
  tickets can be derived without ambiguity.
- It accumulates as historical record (ADR at sprint granularity) at sprint
  close. It is not merged into canonical design docs.

### Files to Modify

- `clasi/plugin/skills/architecture-authoring/SKILL.md` (Mode 2 opening only)

### Testing Plan

No automated test. Manual verification: read the revised SKILL.md and confirm
no retrospective framing appears in Mode 2, and that "before tickets" and the
guiding question are present.

### Documentation Updates

The SKILL.md IS the documentation update for this ticket. Broader docs are
updated in ticket 004.
