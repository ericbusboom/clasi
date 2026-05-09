---
id: "016-015"
title: "Documentation and deprecation: delta-as-historical-record model"
status: todo
use-cases: [SUC-001]
depends-on: ["016-014"]
---

# 016-015: Documentation and deprecation — delta-as-historical-record model

## Description

Complete the transition: `architecture-update.md` is no longer created for
new sprints. Update `create_sprint` (MCP tool / Sprint constructor), remove
any remaining references to `architecture-update.md` from agent prompts and
skills, and update README/docs to explain the delta-as-historical-record
model.

Key documentation points to establish:

- Canonical design docs (`docs/design/specification.md`,
  `docs/design/usecases.md`) are project-init artifacts. They are authored
  ONCE at project initiation. Sprint close does NOT update them. They are
  frozen historical records alongside the deltas.
- "What is the architecture now?" is answered by reading the code — not a
  snapshot doc. The per-sprint deltas are the chronological record of
  structural intent.
- `architecture-delta.md` accumulates under `docs/clasi/sprints/<id>/` and
  travels into `done/<id>/` at close. The delta corpus is the history.
- close-sprint contract is UNCHANGED — no new merge step. The delta is
  preserved as history, nothing is merged into source-of-truth docs.

## Acceptance Criteria

- [ ] `create_sprint` MCP tool creates `architecture-delta.md` from the delta
  template instead of `architecture-update.md`. `architecture-update.md` is
  NOT created for new sprints.
- [ ] All agent prompts and SKILL.md files that previously mentioned
  `architecture-update.md` as a planning output have been updated to
  `architecture-delta.md`. (Audit: grep the codebase for
  `architecture-update.md` and resolve each occurrence.)
- [ ] Existing done/ sprints with `architecture-update.md` are untouched.
- [ ] `Sprint.archive()` still copies `architecture-update.md` to the
  architecture directory if it exists (backward compat for old sprints) — and
  ALSO preserves `architecture-delta.md` in the done/ directory for new-format
  sprints. No merge step added.
- [ ] The SE overview template and/or README explain:
  - Design docs are frozen project-init artifacts, not maintained source-of-truth.
  - "Current architecture" is answered by the code, not a snapshot doc.
  - Deltas accumulate as historical record; close-sprint archives them as-is.
- [ ] The `se-overview-template.md` (if it describes sprint artifacts) is
  updated to reference `architecture-delta.md` and explain the historical-record
  model.
- [ ] All tests pass.

## Implementation Plan

### Approach

1. Update the sprint creation path (find where `architecture-update.md`
   placeholder is created, replace with `architecture-delta.md` from the
   delta template).
2. `grep -r "architecture-update.md" clasi/` to find all references.
3. Update each reference: planning-context references become
   `architecture-delta.md`; archive-context references (copy to architecture
   dir) retain their behavior for backward compat.
4. Update README and se-overview-template.md to document the
   delta-as-historical-record model clearly.
5. Ensure sprint.py archive() preserves `architecture-delta.md` in the done/
   directory (it already does by virtue of moving the whole sprint dir —
   verify this is the case).

### Files to Modify

- `clasi/sprint.py` or wherever `create_sprint` creates the placeholder file
- `clasi/tools/process_tools.py` (if sprint creation logic is here)
- All SKILL.md and agent prompt files with remaining `architecture-update.md`
  references
- `README.md`
- `clasi/se-overview-template.md`

### Testing Plan

- Run the full test suite: `uv run pytest`.
- Verify that a new sprint created via the MCP tool has `architecture-delta.md`
  and no `architecture-update.md`.
- Verify that `clasi sprint validate-delta` works on the newly-created empty
  template file (or reports a clear "empty delta" message, not a traceback).
- Verify that closing a sprint with `architecture-delta.md` moves it intact
  to `done/<id>/architecture-delta.md`.

### Documentation Updates

README and se-overview-template.md are updated in this ticket to explain the
delta-as-historical-record model.
