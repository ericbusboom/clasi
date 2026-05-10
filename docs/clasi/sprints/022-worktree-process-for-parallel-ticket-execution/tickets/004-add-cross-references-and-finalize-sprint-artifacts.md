---
id: "004"
title: "Add cross-references and finalize sprint artifacts"
status: todo
use-cases:
  - SUC-001
  - SUC-005
depends-on:
  - "002"
  - "003"
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add cross-references and finalize sprint artifacts

## Description

Once the design document and stub module exist, ensure the existing serial-only
execution instruction cross-links to the design document, and that the design
document's "Current State" section is accurate. This is a lightweight linking
and finalization ticket — no net-new content, only references and minor prose
updates to connect the new artifact to the existing documentation.

This ticket also closes the source TODO once the design deliverables are
confirmed present and correct.

## Acceptance Criteria

- [ ] Read `clasi/schemas/se-process/instructions/execution.md` and confirm it
      already contains a forward reference to the worktree TODO. If it does,
      update that reference to also point to the new design document
      (`docs/clasi/design/worktree-process.md`). If it does not, add one sentence
      that says "When parallel execution is re-enabled, see
      `docs/clasi/design/worktree-process.md` for the process spec."
- [ ] The design document's `## Current State` preamble (authored in ticket 002)
      accurately reflects the current codebase as audited in ticket 001. If
      anything changed during sprint execution, update the preamble.
- [ ] Confirm `clasi/worktree.py` (from ticket 003) has its module docstring
      pointing to `docs/clasi/design/worktree-process.md`. No change needed if
      it already does; record confirmation in the commit message.
- [ ] `uv run pytest` passes (no regressions from any minor prose changes).
- [ ] Source TODO (`docs/clasi/todo/define-proper-worktree-process-for-parallel-ticket-execution.md`)
      is marked as completed via `move_todo_to_done` MCP call. This is the
      final step and the signal that the sprint's observable deliverable — the
      design document — exists.

## Implementation Plan

### Approach

Read execution.md, check for the existing worktree reference (the current text
says "see docs/clasi/todo/define-proper-worktree-process-...md"). Update that
reference to mention the design document path. Confirm stub module docstring.
Call `move_todo_to_done` for the source TODO.

### Files to modify

- `clasi/schemas/se-process/instructions/execution.md` — update forward reference
- `docs/clasi/design/worktree-process.md` — minor preamble updates if needed

### Files to create

None.

### Documentation updates

Covered by the modifications above.

### Testing Plan

- Run `uv run pytest` to confirm no regressions from the text edit to
  `execution.md`.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: none
- **Verification command**: `uv run pytest`
