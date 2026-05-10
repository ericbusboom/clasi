---
id: "002"
title: "Author worktree-process design document"
status: todo
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
depends-on:
  - "001"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Author worktree-process design document

## Description

Write the authoritative worktree-process design document at
`docs/clasi/design/worktree-process.md`. This document specifies the full
lifecycle for parallel worktree-based ticket execution so that, when parallelism
is re-enabled, the implementation has one clear spec to satisfy.

Use the audit notes from ticket 001 and the architecture-update.md from this
sprint as primary inputs. Cover all eight areas listed in the source TODO.

This sprint is design-only. No code is changed.

## Acceptance Criteria

- [ ] `docs/clasi/design/` directory exists (create if absent).
- [ ] `docs/clasi/design/worktree-process.md` is created with YAML frontmatter
      (`title`, `status: draft`, `sprint: "022"`).
- [ ] Document covers **preconditions for parallel execution**: all conditions
      that must be true before any worktree is created.
- [ ] Document covers **ticket independence determination**: algorithm for
      detecting shared-file and shared-test hazards; defines what "independent"
      means precisely.
- [ ] Document covers **ownership**: explicitly states that the controller
      (team-lead / execute-sprint skill) owns worktree create, branch create,
      merge-back, and cleanup; the programmer agent owns only implementation.
- [ ] Document covers **naming conventions**: worktree path pattern and
      per-ticket branch name pattern with examples.
- [ ] Document covers **pre-completion validation**: the three checks
      (tests pass, clean tree, ticket status done) that must pass before merge.
- [ ] Document covers **merge strategy and conflict resolution**: fast-forward
      preference, merge-commit fallback, no rebase, conflict escalation to
      stakeholder.
- [ ] Document covers **cleanup rules**: on success and on failure/abandonment.
- [ ] Document covers **audit / recovery state**: schema for
      `.worktree-audit.json`, what is written at each lifecycle transition,
      how it is read on recovery.
- [ ] Document covers **hooks vs. controller**: hooks are log-only; all
      enforcement is in controller code.
- [ ] Document covers **error paths**: merge conflict, test failure (with retry
      cap), orphaned worktree, abandoned branch.
- [ ] Document covers **opt-in gate**: the sentinel file mechanism
      (`docs/clasi/.parallel-exec-enabled`).
- [ ] Document includes a state-machine diagram (Mermaid or ASCII) for the
      worktree lifecycle.
- [ ] Open questions from the architecture-update are addressed or carried
      forward in a dedicated `## Open Questions` section.
- [ ] No files outside `docs/clasi/design/` and the sprint directory are
      modified.

## Implementation Plan

### Approach

Write the document directly. Use the architecture-update.md "What Changed"
section for the worktree-process.md content structure and expand each bullet
into full prose. The audit notes from ticket 001 inform the "Current State"
preamble section.

### Files to create

- `docs/clasi/design/worktree-process.md`

### Files to modify

None.

### Documentation updates

The design document IS the documentation deliverable.

### Testing Plan

- No code tests (no code changed).
- Manual review: verify all 15 acceptance criteria checkboxes are satisfiable
  by reading the produced document.

## Testing

- **Existing tests to run**: n/a (no code changes)
- **New tests to write**: none
- **Verification command**: `ls docs/clasi/design/worktree-process.md`
