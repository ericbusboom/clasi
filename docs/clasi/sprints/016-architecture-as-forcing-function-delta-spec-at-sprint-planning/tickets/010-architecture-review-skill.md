---
id: "016-010"
title: "architecture-review skill: parser-first step"
status: todo
use-cases: [SUC-002]
depends-on: ["016-002"]
---

# 016-010: architecture-review skill — parser-first step

## Description

Update `clasi/plugin/skills/architecture-review/SKILL.md` to add a
parser-first Step 0: before any semantic review, run
`clasi sprint validate-delta <id>`. If the parse fails, return REVISE with
the parser error verbatim. Only proceed to semantic review if the delta
parses cleanly.

## Acceptance Criteria

- [ ] `architecture-review/SKILL.md` Process section begins with:
  - Step 0: Run `clasi sprint validate-delta <id>`.
  - If exit code is non-zero: issue REVISE verdict with the parser error
    message quoted verbatim. Stop — do not perform semantic review.
  - If exit code is 0: proceed to Step 1 (read the current architecture)
    as before.
- [ ] The skill handles the case where `architecture-delta.md` is absent
  (e.g., an old-format sprint with only `architecture-update.md`):
  in this case, skip the parser step and proceed with semantic review of
  `architecture-update.md` (backward compatibility for pre-016 sprints).
- [ ] The Verdict section notes that a parse failure always maps to REVISE
  (not APPROVE WITH CHANGES), because format violations are
  blocking, not cosmetic.

## Implementation Plan

### Approach

Edit `clasi/plugin/skills/architecture-review/SKILL.md`. Prepend Step 0 to
the Process section. Add a conditional for the file-absent case.

### Files to Modify

- `clasi/plugin/skills/architecture-review/SKILL.md`

### Testing Plan

No automated test for SKILL.md content. Verify manually that the Step 0
instructions are unambiguous.

### Documentation Updates

The SKILL.md IS the documentation update.
